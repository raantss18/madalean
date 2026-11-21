// Hide the console window on Windows release builds (not a target today, harmless elsewhere).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    madalean_desktop::run()
}
