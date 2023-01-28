use std::error;
use std::io::Cursor;

use async_trait::async_trait;
use azalea::prelude::*;
use azalea_buf::{McBufReadable, McBufWritable, UnsizedByteArray};
use azalea_core::ResourceLocation;
use azalea_protocol::packets::game::{ClientboundGamePacket, ServerboundGamePacket};
use azalea_protocol::packets::game::serverbound_custom_payload_packet::ServerboundCustomPayloadPacket;
use const_format::formatcp;
use log::{error, info};

use crate::secret::{SecretRequest, SecretResponse, VOICECHAT_REQUEST_SECRET_CHANNEL, VOICECHAT_SECRET_CHANNEL};

mod respawn;
mod plugin_channels;
mod secret;

#[macro_use]
mod resource_location;

const MINECRAFT_NAMESPACE: &str = "minecraft";
const MINECRAFT_BRAND_CHANNEL: &str = resource_location!(MINECRAFT_NAMESPACE, "brand");

const VOICECHAT_COMPAT_VERSION: i32 = 15;

#[tokio::main]
async fn main() {
    env_logger::init();
    let account = Account::offline("Raqbot");

    azalea::start(azalea::Options {
        account,
        address: "localhost:25565",
        plugins: plugins![
            respawn::Plugin::default(),
            plugin_channels::Plugin::require_plugins(vec![
                VOICECHAT_REQUEST_SECRET_CHANNEL,
                VOICECHAT_SECRET_CHANNEL
            ])
        ],
        state: State::default(),
        handle,
    })
        .await
        .unwrap_or_else(|e| {
            println!("Could not start bot: {}", e)
        })
}

#[async_trait]
pub trait ClientPMExt {
    async fn write_plugin_message<T: McBufWritable + Send>(self, identifier: &str, data: T) -> Result<(), Box<dyn error::Error>>;
}

#[async_trait]
impl ClientPMExt for Client {
    async fn write_plugin_message<T: McBufWritable + Send>(self, identifier: &str, data: T) -> Result<(), Box<dyn error::Error>> {
        let mut buf = Vec::new();
        data.write_into(&mut buf)?;

        let identifier = ResourceLocation::new(identifier)?;

        let packet = ServerboundCustomPayloadPacket {
            identifier,
            data: UnsizedByteArray::from(buf),
        };
        self.write_packet(ServerboundGamePacket::CustomPayload(packet)).await?;
        Ok(())
    }
}

#[derive(Default, Clone)]
pub struct State {}

async fn handle(client: Client, event: Event, state: State) -> anyhow::Result<()> {
    match event {
        Event::Chat(m) => {
            info!("{}", m.message().to_ansi(None));
        }
        Event::Packet(packet) => {
            handle_packet(client, state, packet).await;
        }
        _ => {}
    }
    Ok(())
}

async fn handle_packet(client: Client, state: State, pkt: Box<ClientboundGamePacket>) {
    if let ClientboundGamePacket::CustomPayload(packet) = *pkt {
        match packet.identifier.to_string().as_str() {
            MINECRAFT_BRAND_CHANNEL => {
                match client.write_plugin_message(
                    VOICECHAT_REQUEST_SECRET_CHANNEL,
                    SecretRequest {
                        compat_version: VOICECHAT_COMPAT_VERSION
                    },
                ).await {
                    Ok(_) => { info!("Sent secret request") }
                    Err(e) => error!("Could not send secret request: {}", e)
                }
            }
            VOICECHAT_SECRET_CHANNEL => {
                match SecretResponse::read_from(&mut Cursor::new(&*packet.data)) {
                    Ok(resp) => {
                        info!("Secret response: {:?}", resp)
                    }
                    Err(e) => {
                        error!("Could not parse secret response: {}", e)
                    }
                }
            }
            _ => {}
        }
    }
}
