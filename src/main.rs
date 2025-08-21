use crossbeam_channel::{unbounded, Receiver, Sender, TryRecvError};
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use slint::{VecModel, SharedString};
use std::thread;
use tokio::runtime::Runtime;
use tokio::sync::mpsc::UnboundedSender;
use url::Url;

// Include UI
slint::include_modules!();

// Backend server URL (same as original)
const SERVER_URL: &str = "wss://termchat-f9cgabe4ajd9djb9.australiaeast-01.azurewebsites.net";

#[derive(Debug)]
enum NetCommand {
    Connect {
        username: String,
        chat: String,
        password: String,
    },
    SendText(String),
    Disconnect,
    RequestGeneralCount,
}

#[derive(Debug)]
enum UiEvent {
    Connected,
    Disconnected,
    Received(String),
    Error(String),
    ThemeChange(String),
    BackgroundChange(String),
    ClearChat,
    Kick(String),
    AuthFailed(String),
    GeneralCount(i32),
}

fn spawn_network_thread(net_rx: Receiver<NetCommand>, ui_tx: Sender<UiEvent>) {
    thread::spawn(move || {
        // Create tokio runtime in this thread
        let rt = Runtime::new().expect("failed to create tokio runtime");

        // Outgoing channel sender for the currently active WebSocket connection
        let mut outgoing_tx_opt: Option<UnboundedSender<String>> = None;

        // Track connected state (to notify UI upon connect/disconnect)
        let mut connection_active = false;

        loop {
            match net_rx.recv() {
                Ok(cmd) => match cmd {
                    NetCommand::RequestGeneralCount => {
                        // Perform blocking HTTP get in a separate thread so we don't block network thread
                        let ui_tx_clone = ui_tx.clone();
                        thread::spawn(move || {
                            let gc = fetch_general_count_blocking(SERVER_URL);
                            let _ = ui_tx_clone.send(UiEvent::GeneralCount(gc as i32));
                        });
                    }
                    NetCommand::Connect { username, chat, password } => {
                        // If already connected, ignore
                        if connection_active {
                            let _ = ui_tx.send(UiEvent::Error("Already connected".into()));
                            continue;
                        }

                        // Perform async connect logic using runtime.block_on to obtain outgoing sender
                        let ui_tx_clone = ui_tx.clone();
                        let server_url = SERVER_URL.to_string();
                        match rt.block_on(async move {
                            connect_ws(&server_url, &username, &chat, &password, ui_tx_clone).await
                        }) {
                            Ok(tx) => {
                                outgoing_tx_opt = Some(tx);
                                connection_active = true;
                                // UI will receive Connected when server sends join confirmation (handled in read loop)
                            }
                            Err(e) => {
                                let _ = ui_tx.send(UiEvent::Error(format!("Connect failed: {}", e)));
                            }
                        }
                    }
                    NetCommand::SendText(text) => {
                        if let Some(tx) = &outgoing_tx_opt {
                            // send a message JSON to outgoing writer
                            let msg = serde_json::json!({
                                "type": "message",
                                "content": text
                            })
                            .to_string();
                            // UnboundedSender::send is immediate
                            let _ = tx.send(msg);
                        } else {
                            let _ = ui_tx.send(UiEvent::Error("Not connected".into()));
                        }
                    }
                    NetCommand::Disconnect => {
                        if let Some(tx) = &outgoing_tx_opt {
                            // send a close request token for writer to close the socket
                            let _ = tx.send("__TERMCHAT__CLOSE__".into());
                        }
                        outgoing_tx_opt = None;
                        if connection_active {
                            connection_active = false;
                            let _ = ui_tx.send(UiEvent::Disconnected);
                        }
                    }
                },
                Err(_) => {
                    // net_rx sender dropped => exit thread
                    break;
                }
            }
        }
    });
}

// Blocking general count helper (uses reqwest blocking)
fn fetch_general_count_blocking(server_url: &str) -> u32 {
    // convert wss://host/... to https://host and call /general-count
    if let Ok(url) = Url::parse(server_url) {
        if let Some(host) = url.host_str() {
            let endpoint = format!("https://{}/general-count", host);
            let client = Client::builder().timeout(std::time::Duration::from_secs(3)).build();
            if let Ok(client) = client {
                if let Ok(resp) = client.get(&endpoint).send() {
                    if resp.status().is_success() {
                        if let Ok(json) = resp.json::<serde_json::Value>() {
                            if let Some(count) = json.get("userCount").and_then(|v| v.as_u64()) {
                                return count as u32;
                            }
                        }
                    }
                }
            }
        }
    }
    0
}

// Connect to websocket and spawn reader/writer tasks. Returns an UnboundedSender for outgoing messages.
async fn connect_ws(
    server_url: &str,
    username: &str,
    chat: &str,
    password: &str,
    ui_tx: Sender<UiEvent>,
) -> Result<UnboundedSender<String>, Box<dyn std::error::Error + Send + Sync>> {
    use futures_util::{SinkExt, StreamExt};
    use tokio_tungstenite::connect_async;
    use tokio_tungstenite::tungstenite::protocol::Message as WsMessage;

    let url = Url::parse(server_url)?;

    let (ws_stream, _resp) = connect_async(url).await?;
    let (mut write, mut read) = ws_stream.split();

    // outgoing channel (unbounded) used by the synchronous network thread to push outgoing messages
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<String>();

    let ui_tx_read = ui_tx.clone();

    // Reader task
    tokio::spawn(async move {
        while let Some(message) = read.next().await {
            match message {
                Ok(WsMessage::Text(txt)) => {
                    // Parse JSON and send appropriate UiEvent
                    if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&txt) {
                        if let Some(t) = parsed.get("type").and_then(|v| v.as_str()) {
                            match t {
                                "message" => {
                                    let username = parsed.get("username").and_then(|v| v.as_str()).unwrap_or("Unknown");
                                    let content = parsed.get("content").and_then(|v| v.as_str()).unwrap_or("");
                                    let display = if username.eq_ignore_ascii_case("server") {
                                        format!("Server: {}", content)
                                    } else {
                                        format!("[{}] {}", username, content)
                                    };
                                    let _ = ui_tx_read.send(UiEvent::Received(display));
                                }
                                "join" => {
                                    if let Some(username) = parsed.get("username").and_then(|v| v.as_str()) {
                                        let _ = ui_tx_read.send(UiEvent::Received(format!("[System] {} joined", username)));
                                    }
                                }
                                "leave" => {
                                    if let Some(username) = parsed.get("username").and_then(|v| v.as_str()) {
                                        let _ = ui_tx_read.send(UiEvent::Received(format!("[System] {} left", username)));
                                    }
                                }
                                "colourshift" | "colourshift" => {
                                    if let Some(color) = parsed.get("color").and_then(|v| v.as_str()) {
                                        let _ = ui_tx_read.send(UiEvent::ThemeChange(color.to_string()));
                                    }
                                }
                                "bgshift" => {
                                    if let Some(color) = parsed.get("color").and_then(|v| v.as_str()) {
                                        let _ = ui_tx_read.send(UiEvent::BackgroundChange(color.to_string()));
                                    }
                                }
                                "chatclear" => {
                                    let _ = ui_tx_read.send(UiEvent::ClearChat);
                                }
                                "kicked" => {
                                    let msg = parsed.get("message").and_then(|v| v.as_str()).unwrap_or("You have been kicked");
                                    let _ = ui_tx_read.send(UiEvent::Kick(msg.to_string()));
                                }
                                "error" => {
                                    let err = parsed.get("message").and_then(|v| v.as_str()).unwrap_or("Unknown error");
                                    let _ = ui_tx_read.send(UiEvent::Error(err.to_string()));
                                }
                                "auth_failed" => {
                                    let err = parsed.get("message").and_then(|v| v.as_str()).unwrap_or("Authentication failed");
                                    let _ = ui_tx_read.send(UiEvent::AuthFailed(err.to_string()));
                                }
                                _ => {
                                    let _ = ui_tx_read.send(UiEvent::Received(txt.clone()));
                                }
                            }
                        } else {
                            let _ = ui_tx_read.send(UiEvent::Received(txt.clone()));
                        }
                    } else {
                        let _ = ui_tx_read.send(UiEvent::Received(txt.clone()));
                    }
                }
                Ok(WsMessage::Close(_)) => {
                    let _ = ui_tx_read.send(UiEvent::Disconnected);
                    break;
                }
                Ok(_) => {}
                Err(e) => {
                    let _ = ui_tx_read.send(UiEvent::Error(format!("WS receive error: {}", e)));
                    break;
                }
            }
        }
    });

    // Writer task
    let ui_tx_write = ui_tx.clone();
    tokio::spawn(async move {
        while let Some(msg) = rx.recv().await {
            if msg == "__TERMCHAT__CLOSE__" {
                let _ = write.send(WsMessage::Close(None)).await;
                break;
            }
            if let Err(e) = write.send(WsMessage::Text(msg)).await {
                let _ = ui_tx_write.send(UiEvent::Error(format!("WS send error: {}", e)));
                break;
            }
        }
    });

    // Immediately send join message via tx
    let join_msg = serde_json::json!({
        "type": "join",
        "username": username,
        "chatname": chat,
        "password": password
    })
    .to_string();
    let _ = tx.send(join_msg);

    Ok(tx)
}

fn main() {
    let (net_tx, net_rx) = unbounded::<NetCommand>();
    let (ui_tx, ui_rx) = unbounded::<UiEvent>();

    spawn_network_thread(net_rx, ui_tx);

    let main_window = MainWindow::new();
    let messages_model = VecModel::from(Vec::<SharedString>::new());
    main_window.set_messages(messages_model.clone().into());

    main_window.set_connected(false);
    main_window.set_header_text("TERMCHAT - Not connected".into());
    main_window.set_theme_color("#87CEEB".into());
    main_window.set_background_color("#000000".into());
    main_window.set_general_count(-1i32);

    let net_tx_connect = net_tx.clone();
    let net_tx_send = net_tx.clone();
    let net_tx_disconnect = net_tx.clone();
    let net_tx_request_gc = net_tx.clone();

    main_window.on_connect(move |username, chat, password| {
        let u = if username.trim().is_empty() { "guest".into() } else { username.to_string() };
        let _ = net_tx_connect.send(NetCommand::Connect {
            username: u,
            chat: if chat.trim().is_empty() { "general".into() } else { chat.to_string() },
            password: if password.trim().is_empty() { "default".into() } else { password.to_string() },
        });
    });

    {
        let messages_model_clone = messages_model.clone();
        main_window.on_send_message(move |text| {
            if text.trim().is_empty() {
                return;
            }
            messages_model_clone.push_back(SharedString::from(format!("[me] {}", text)));
            let _ = net_tx_send.send(NetCommand::SendText(text.to_string()));
        });
    }

    main_window.on_disconnect(move || {
        let _ = net_tx_disconnect.send(NetCommand::Disconnect);
    });

    main_window.on_request_general_count(move || {
        let _ = net_tx_request_gc.send(NetCommand::RequestGeneralCount);
    });

    {
        let messages_model_for_poll = messages_model.clone();
        let ui_rx_for_poll = ui_rx.clone();
        main_window.on_poll_network(move || {
            loop {
                match ui_rx_for_poll.try_recv() {
                    Ok(evt) => match evt {
                        UiEvent::Connected => {
                            main_window.set_connected(true);
                            main_window.set_header_text("TERMCHAT - Connected".into());
                            messages_model_for_poll.push_back(SharedString::from("[System] Connected."));
                        }
                        UiEvent::Disconnected => {
                            main_window.set_connected(false);
                            main_window.set_header_text("TERMCHAT - Disconnected".into());
                            messages_model_for_poll.push_back(SharedString::from("[System] Disconnected."));
                        }
                        UiEvent::Received(txt) => {
                            messages_model_for_poll.push_back(SharedString::from(txt));
                        }
                        UiEvent::Error(err) => {
                            messages_model_for_poll.push_back(SharedString::from(format!("[Error] {}", err)));
                        }
                        UiEvent::ThemeChange(color) => {
                            main_window.set_theme_color(color.clone().into());
                            messages_model_for_poll.push_back(SharedString::from(format!("[System] Theme color changed to {}", color)));
                        }
                        UiEvent::BackgroundChange(color) => {
                            main_window.set_background_color(color.clone().into());
                            messages_model_for_poll.push_back(SharedString::from(format!("[System] Background changed")));
                        }
                        UiEvent::ClearChat => {
                            messages_model_for_poll.clear();
                        }
                        UiEvent::Kick(msg) => {
                            messages_model_for_poll.clear();
                            messages_model_for_poll.push_back(SharedString::from(format!("[Kicked] {}", msg)));
                        }
                        UiEvent::AuthFailed(msg) => {
                            messages_model_for_poll.push_back(SharedString::from(format!("[Auth Failed] {}", msg)));
                            main_window.set_connected(false);
                        }
                        UiEvent::GeneralCount(n) => {
                            main_window.set_general_count(n);
                        }
                    },
                    Err(TryRecvError::Empty) => break,
                    Err(TryRecvError::Disconnected) => {
                        messages_model_for_poll.push_back(SharedString::from("[System] Network channel closed"));
                        break;
                    }
                }
            }
        });
    }

    main_window.run();
}
