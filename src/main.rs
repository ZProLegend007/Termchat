mod websocket;
mod message;
mod app_state;
mod colors;

use slint::{ComponentHandle, Model, ModelRc, VecModel};
use std::sync::{Arc, Mutex};
use tokio::sync::mpsc;
use tokio::time::{sleep, Duration};

slint::include_modules!();

use app_state::{AppState, AppEvent, Screen};
use colors::UserColors;
use message::{ServerMessage, ClientMessage};
use websocket::WebSocketManager;

const SERVER_URL: &str = "wss://termchat-f9cgabe4ajd9djb9.australiaeast-01.azurewebsites.net";

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let app = App::new()?;
    let app_weak = app.as_weak();
    
    let (event_sender, mut event_receiver) = mpsc::unbounded_channel::<AppEvent>();
    let app_state = Arc::new(Mutex::new(AppState::new()));
    let user_colors = Arc::new(Mutex::new(UserColors::new()));
    let messages_model = ModelRc::new(VecModel::<ChatMessage>::default());
    
    // Set initial state
    app.set_current_screen("splash".into());
    app.set_messages(messages_model.clone());
    
    // Setup callbacks
    {
        let event_sender = event_sender.clone();
        app.on_splash_complete(move || {
            let _ = event_sender.send(AppEvent::SplashComplete);
        });
    }
    
    {
        let event_sender = event_sender.clone();
        app.on_connect_requested(move |username, chatname, password| {
            let _ = event_sender.send(AppEvent::ConnectRequested {
                username: username.to_string(),
                chatname: chatname.to_string(),
                password: password.to_string(),
            });
        });
    }
    
    {
        let event_sender = event_sender.clone();
        app.on_send_message(move |message| {
            let _ = event_sender.send(AppEvent::SendMessage(message.to_string()));
        });
    }
    
    {
        let event_sender = event_sender.clone();
        app.on_quit_requested(move || {
            let _ = event_sender.send(AppEvent::Quit);
        });
    }
    
    {
        let event_sender = event_sender.clone();
        app.on_clear_messages(move || {
            let _ = event_sender.send(AppEvent::ClearMessages);
        });
    }
    
    // Start server status check
    let status_sender = event_sender.clone();
    tokio::spawn(async move {
        loop {
            let available = check_server_status().await;
            let _ = status_sender.send(AppEvent::ServerStatusUpdate(available));
            sleep(Duration::from_secs(5)).await;
        }
    });
    
    // Start general count updater
    let count_sender = event_sender.clone();
    tokio::spawn(async move {
        loop {
            let count = get_general_count().await;
            let _ = count_sender.send(AppEvent::GeneralCountUpdate(count));
            sleep(Duration::from_secs(10)).await;
        }
    });
    
    let mut websocket_manager: Option<WebSocketManager> = None;
    
    // Main event loop
    let event_loop = async move {
        while let Some(event) = event_receiver.recv().await {
            if let Some(app) = app_weak.upgrade() {
                match event {
                    AppEvent::SplashComplete => {
                        app.set_current_screen("connection".into());
                        let mut state = app_state.lock().unwrap();
                        state.set_screen(Screen::Connection);
                    }
                    
                    AppEvent::ServerStatusUpdate(available) => {
                        app.set_server_available(available);
                        app.set_server_status(
                            if available { "Server available" } else { "Server unavailable" }.into()
                        );
                    }
                    
                    AppEvent::GeneralCountUpdate(count) => {
                        app.set_general_count(count);
                    }
                    
                    AppEvent::ConnectRequested { username, chatname, password } => {
                        let final_username = if username.trim().is_empty() { "guest" } else { username.trim() };
                        let final_chatname = if chatname.trim().is_empty() { "general" } else { chatname.trim() };
                        let final_password = if password.trim().is_empty() { "default" } else { password.trim() };
                        
                        if final_username.to_lowercase() == "server" {
                            // Show error for forbidden username
                            continue;
                        }
                        
                        app.set_chat_name(final_chatname.into());
                        app.set_current_screen("chat".into());
                        app.set_connection_status("Connecting...".into());
                        
                        // Clear messages
                        messages_model.as_any().downcast_ref::<VecModel<ChatMessage>>()
                            .unwrap().set_vec(vec![]);
                        
                        // Start WebSocket connection
                        let ws_manager = WebSocketManager::new(
                            SERVER_URL.to_string(),
                            final_username.to_string(),
                            final_chatname.to_string(),
                            final_password.to_string(),
                            event_sender.clone(),
                        );
                        
                        tokio::spawn(async move {
                            if let Err(e) = ws_manager.connect().await {
                                eprintln!("WebSocket connection failed: {}", e);
                            }
                        });
                        
                        let mut state = app_state.lock().unwrap();
                        state.set_screen(Screen::Chat);
                        state.set_username(final_username.to_string());
                        state.set_chatname(final_chatname.to_string());
                    }
                    
                    AppEvent::Connected => {
                        app.set_connection_status("Connected".into());
                    }
                    
                    AppEvent::Disconnected => {
                        app.set_connection_status("Disconnected".into());
                    }
                    
                    AppEvent::MessageReceived { username, content, is_server } => {
                        let color = if is_server {
                            slint::Color::from_rgb_u8(135, 206, 235) // Primary color for server
                        } else {
                            let mut colors = user_colors.lock().unwrap();
                            colors.get_color(&username)
                        };
                        
                        let chat_message = ChatMessage {
                            username: username.into(),
                            content: content.into(),
                            color,
                            is_server,
                        };
                        
                        let model = messages_model.as_any().downcast_ref::<VecModel<ChatMessage>>().unwrap();
                        model.push(chat_message);
                    }
                    
                    AppEvent::SendMessage(content) => {
                        // Handle special commands
                        match content.trim().to_lowercase().as_str() {
                            "/clear" | "/c" => {
                                messages_model.as_any().downcast_ref::<VecModel<ChatMessage>>()
                                    .unwrap().set_vec(vec![]);
                                continue;
                            }
                            "/quit" | "/exit" | "/q" => {
                                break;
                            }
                            _ => {}
                        }
                        
                        if let Some(ref mut ws_manager) = websocket_manager {
                            let message = ClientMessage::Message { content };
                            if let Err(e) = ws_manager.send_message(message).await {
                                eprintln!("Failed to send message: {}", e);
                            }
                        }
                    }
                    
                    AppEvent::ClearMessages => {
                        messages_model.as_any().downcast_ref::<VecModel<ChatMessage>>()
                            .unwrap().set_vec(vec![]);
                    }
                    
                    AppEvent::Quit => {
                        break;
                    }
                    
                    _ => {} // Handle other events as needed
                }
            }
        }
    };
    
    // Run both the UI and event loop
    tokio::select! {
        _ = app.run() => {},
        _ = event_loop => {}
    }
    
    Ok(())
}

async fn check_server_status() -> bool {
    match tokio_tungstenite::connect_async(SERVER_URL).await {
        Ok((ws_stream, _)) => {
            drop(ws_stream);
            true
        }
        Err(_) => false,
    }
}

async fn get_general_count() -> i32 {
    let http_url = SERVER_URL.replace("wss://", "https://")
        .split('/')
        .next()
        .map(|host| format!("https://{}/general-count", host))
        .unwrap_or_default();
    
    match reqwest::get(&http_url).await {
        Ok(response) => {
            if let Ok(json) = response.json::<serde_json::Value>().await {
                json.get("userCount")
                    .and_then(|v| v.as_i64())
                    .map(|v| v as i32)
                    .unwrap_or(0)
            } else {
                0
            }
        }
        Err(_) => 0,
    }
}
