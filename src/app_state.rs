#[derive(Debug, Clone)]
pub enum Screen {
    Splash,
    Connection,
    Chat,
}

#[derive(Debug, Clone)]
pub enum AppEvent {
    SplashComplete,
    ServerStatusUpdate(bool),
    GeneralCountUpdate(i32),
    ConnectRequested {
        username: String,
        chatname: String,
        password: String,
    },
    Connected,
    Disconnected,
    MessageReceived {
        username: String,
        content: String,
        is_server: bool,
    },
    SendMessage(String),
    ClearMessages,
    UserJoined(String),
    UserLeft(String),
    ThemeColorChange(String),
    BackgroundColorChange(String),
    Kicked(String),
    Quit,
}

pub struct AppState {
    pub screen: Screen,
    pub username: String,
    pub chatname: String,
    pub connected: bool,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            screen: Screen::Splash,
            username: String::new(),
            chatname: String::new(),
            connected: false,
        }
    }
    
    pub fn set_screen(&mut self, screen: Screen) {
        self.screen = screen;
    }
    
    pub fn set_username(&mut self, username: String) {
        self.username = username;
    }
    
    pub fn set_chatname(&mut self, chatname: String) {
        self.chatname = chatname;
    }
    
    pub fn set_connected(&mut self, connected: bool) {
        self.connected = connected;
    }
}
```

## src/message.rs

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum ClientMessage {
    #[serde(rename = "join")]
    Join {
        username: String,
        chatname: String,
        password: String,
    },
    #[serde(rename = "message")]
    Message {
        content: String,
    },
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type")]
pub enum ServerMessage {
    #[serde(rename = "join")]
    Join {
        username: String,
    },
    #[serde(rename = "leave")]
    Leave {
        username: String,
    },
    #[serde(rename = "message")]
    Message {
        username: String,
        content: String,
    },
    #[serde(rename = "error")]
    Error {
        message: String,
    },
    #[serde(rename = "auth_failed")]
    AuthFailed {
        message: String,
    },
    #[serde(rename = "colourshift")]
    ColorShift {
        color: String,
    },
    #[serde(rename = "bgshift")]
    BackgroundShift {
        color: String,
    },
    #[serde(rename = "chatclear")]
    ChatClear,
    #[serde(rename = "kicked")]
    Kicked {
        message: String,
    },
}
