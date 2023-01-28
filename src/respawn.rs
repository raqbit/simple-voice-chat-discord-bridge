//! Automatically respawn when we die

use async_trait::async_trait;
use azalea::{Client, Event};
use azalea_protocol::packets::game::{
    serverbound_client_command_packet::Action,
    serverbound_client_command_packet::ServerboundClientCommandPacket, ClientboundGamePacket,
    ServerboundGamePacket,
};

#[derive(Default, Clone)]
pub struct Plugin {}

#[async_trait]
impl azalea::Plugin for Plugin {
    async fn handle(self: Box<Self>, event: Event, bot: Client) {
        if let Event::Packet(p) = event {
            if let ClientboundGamePacket::SetHealth(h) = *p {
                if h.health == 0.0 {
                    bot.write_packet(ServerboundGamePacket::ClientCommand(
                        ServerboundClientCommandPacket {
                            action: Action::PerformRespawn,
                        },
                    ))
                    .await
                    .unwrap_or_else(|_| {}) // Ignore errors, we can't really do anything about them
                }
            }
        }
    }
}
