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
    MessageReceived {
        username: String,
        content: String,
        is_server: bool,
    },
    SendMessage(String),
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
}
