use crate::message::{ClientMessage, ServerMessage};
use crate::app_state::AppEvent;
use futures_util::{SinkExt, StreamExt};
use tokio::sync::mpsc;
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};

pub struct WebSocketManager {
    server_url: String,
    username: String,
    chatname: String,
    password: String,
    event_sender: mpsc::UnboundedSender<AppEvent>,
}

impl WebSocketManager {
    pub fn new(
        server_url: String,
        username: String,
        chatname: String,
        password: String,
        event_sender: mpsc::UnboundedSender<AppEvent>,
    ) -> Self {
        Self {
            server_url,
            username,
            chatname,
            password,
            event_sender,
        }
    }
    
    pub async fn connect(self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let (ws_stream, _) = connect_async(&self.server_url).await?;
        let (mut write, mut read) = ws_stream.split();
        
        // Send join message
        let join_message = ClientMessage::Join {
            username: self.username.clone(),
            chatname: self.chatname.clone(),
            password: self.password.clone(),
        };
        
        let join_json = serde_json::to_string(&join_message)?;
        write.send(Message::Text(join_json)).await?;
        
        let event_sender = self.event_sender.clone();
        let username = self.username.clone();
        
        // Handle incoming messages
        while let Some(message) = read.next().await {
            match message {
                Ok(Message::Text(text)) => {
                    if let Ok(server_message) = serde_json::from_str::<ServerMessage>(&text) {
                        match server_message {
                            ServerMessage::Join { username: joined_user } => {
                                if joined_user == username {
                                    let _ = event_sender.send(AppEvent::Connected);
                                } else {
                                    let _ = event_sender.send(AppEvent::UserJoined(joined_user));
                                }
                            }
                            ServerMessage::Leave { username: left_user } => {
                                let _ = event_sender.send(AppEvent::UserLeft(left_user));
                            }
                            ServerMessage::Message { username: msg_user, content } => {
                                let is_server = msg_user.to_lowercase() == "server";
                                let _ = event_sender.send(AppEvent::MessageReceived {
                                    username: msg_user,
                                    content,
                                    is_server,
                                });
                            }
                            ServerMessage::Error { message } => {
                                eprintln!("Server error: {}", message);
                                let _ = event_sender.send(AppEvent::Disconnected);
                            }
                            ServerMessage::AuthFailed { message } => {
                                eprintln!("Auth failed: {}", message);
                                let _ = event_sender.send(AppEvent::Disconnected);
                            }
                            ServerMessage::ColorShift { color } => {
                                let _ = event_sender.send(AppEvent::ThemeColorChange(color));
                            }
                            ServerMessage::BackgroundShift { color } => {
                                let _ = event_sender.send(AppEvent::BackgroundColorChange(color));
                            }
                            ServerMessage::ChatClear => {
                                let _ = event_sender.send(AppEvent::ClearMessages);
                            }
                            ServerMessage::Kicked { message } => {
                                let _ = event_sender.send(AppEvent::Kicked(message));
                            }
                        }
                    }
                }
                Ok(Message::Close(_)) => {
                    let _ = event_sender.send(AppEvent::Disconnected);
                    break;
                }
                Err(e) => {
                    eprintln!("WebSocket error: {}", e);
                    let _ = event_sender.send(AppEvent::Disconnected);
                    break;
                }
                _ => {}
            }
        }
        
        Ok(())
    }
    
    pub async fn send_message(&mut self, _message: ClientMessage) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        // This would need to be implemented with a proper connection handle
        // For now, this is a placeholder
        Ok(())
    }
}
