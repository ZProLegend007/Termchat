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
        
        let join_message = ClientMessage::Join {
            username: self.username.clone(),
            chatname: self.chatname.clone(),
            password: self.password.clone(),
        };
        
        let join_json = serde_json::to_string(&join_message)?;
        write.send(Message::Text(join_json)).await?;
        
        let _ = self.event_sender.send(AppEvent::Connected);
        
        while let Some(message) = read.next().await {
            match message {
                Ok(Message::Text(text)) => {
                    if let Ok(server_message) = serde_json::from_str::<ServerMessage>(&text) {
                        match server_message {
                            ServerMessage::Message { username, content } => {
                                let is_server = username.to_lowercase() == "server";
                                let _ = self.event_sender.send(AppEvent::MessageReceived {
                                    username,
                                    content,
                                    is_server,
                                });
                            }
                        }
                    }
                }
                Ok(Message::Close(_)) => break,
                Err(_) => break,
                _ => {}
            }
        }
        
        Ok(())
    }
}
