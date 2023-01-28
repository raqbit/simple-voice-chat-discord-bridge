//! Handles signals to shutdown bot

use async_trait::async_trait;
use azalea::{Client, Event};
use log::{error, info};
use tokio::signal;

#[derive(Default, Clone)]
pub struct Plugin {}

#[async_trait]
impl azalea::Plugin for Plugin {
    async fn handle(self: Box<Self>, event: Event, bot: Client) {
        match event {
            Event::Initialize => {
                match signal::ctrl_c().await {
                    Ok(()) => {}
                    Err(err) => {
                        error!("Unable to listen for shutdown signal: {}", err);
                        // If we're unable to listen for the shutdown signal, we accept not cleanly shutting down
                        return
                    }
                }

                info!("Shutting down");
                bot.shutdown().await.expect("should be able to shutdown");
            },
            _ => {}
        }
    }
}
