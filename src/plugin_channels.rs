//! Require certain plugin channels to be present on the server

use core::str;
use std::collections::HashSet;

use async_trait::async_trait;
use azalea::{Client, Event};
use azalea_protocol::packets::game::clientbound_custom_payload_packet::ClientboundCustomPayloadPacket;
use azalea_protocol::packets::game::ClientboundGamePacket;
use log::{error, info};

#[derive(Default, Clone)]
pub struct Plugin {
    required_plugins: HashSet<&'static str>,
}

impl Plugin {
    pub fn require_plugins(plugins: Vec<&'static str>) -> Plugin {
        Plugin {
            required_plugins: HashSet::from_iter(plugins),
        }
    }
}

#[async_trait]
impl azalea::Plugin for Plugin {
    async fn handle(self: Box<Self>, event: Event, bot: Client) {
        if let Event::Packet(p) = event {
            if let ClientboundGamePacket::CustomPayload(packet) = *p {
                self.handle_custom_payload_packet(bot, packet).await;
            }
        }
    }
}

impl Plugin {
    async fn handle_custom_payload_packet(
        self,
        bot: Client,
        packet: ClientboundCustomPayloadPacket,
    ) {
        match packet.identifier.to_string().as_str() {
            "minecraft:register" => {
                let server_channels: HashSet<&str> = packet
                    .data
                    .split(|&c| c == 0x00)
                    .filter(|x| !x.is_empty())
                    .map(|d| str::from_utf8(d))
                    .filter_map(|x| x.ok())
                    .collect();

                if !self.required_plugins.is_subset(&server_channels) {
                    error!("Server is missing required plugin channels.");
                    bot.shutdown().await.expect("Could not shutdown properly");
                } else {
                    info!(
                        "Required plugin channels present: {}",
                        self.required_plugins
                            .into_iter()
                            .collect::<Vec<&str>>()
                            .join(",")
                    )
                }
            }
            _ => {}
        }
    }
}
