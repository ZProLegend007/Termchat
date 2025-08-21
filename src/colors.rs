use slint::Color;
use std::collections::HashMap;

pub struct UserColors {
    colors: Vec<Color>,
    user_colors: HashMap<String, Color>,
    next_color_index: usize,
}

impl UserColors {
    pub fn new() -> Self {
        let colors = vec![
            Color::from_rgb_u8(255, 0, 0),     // red
            Color::from_rgb_u8(0, 255, 0),     // green
            Color::from_rgb_u8(255, 255, 0),   // yellow
            Color::from_rgb_u8(255, 0, 255),   // magenta
            Color::from_rgb_u8(0, 255, 255),   // cyan
            Color::from_rgb_u8(255, 100, 100), // bright_red
            Color::from_rgb_u8(255, 255, 100), // bright_yellow
            Color::from_rgb_u8(255, 100, 255), // bright_magenta
            Color::from_rgb_u8(100, 255, 255), // bright_cyan
        ];
        
        Self {
            colors,
            user_colors: HashMap::new(),
            next_color_index: 0,
        }
    }
    
    pub fn get_color(&mut self, username: &str) -> Color {
        if username.to_lowercase() == "server" {
            return Color::from_rgb_u8(135, 206, 235); // Primary color
        }
        
        if let Some(&color) = self.user_colors.get(username) {
            return color;
        }
        
        let color = self.colors[self.next_color_index % self.colors.len()];
        self.user_colors.insert(username.to_string(), color);
        self.next_color_index += 1;
        
        color
    }
}
