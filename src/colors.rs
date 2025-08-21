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
            Color::from_rgb_u8(255, 0, 0),
            Color::from_rgb_u8(0, 255, 0),
            Color::from_rgb_u8(255, 255, 0),
            Color::from_rgb_u8(255, 0, 255),
            Color::from_rgb_u8(0, 255, 255),
        ];
        
        Self {
            colors,
            user_colors: HashMap::new(),
            next_color_index: 0,
        }
    }
    
    pub fn get_color(&mut self, username: &str) -> Color {
        if let Some(&color) = self.user_colors.get(username) {
            return color;
        }
        
        let color = self.colors[self.next_color_index % self.colors.len()];
        self.user_colors.insert(username.to_string(), color);
        self.next_color_index += 1;
        
        color
    }
}
