use std::io::Cursor;
use std::ops::Deref;
use std::sync::{Arc, RwLock};

use azalea::prelude::*;
use azalea_buf::McBufReadable;
use azalea_protocol::packets::game::ClientboundGamePacket;
use const_format::formatcp;
use log::{error, info};

use crate::plugin_message::ClientPluginMessageExt;
use crate::secret::{
    SecretRequest, SecretResponse, VOICECHAT_REQUEST_SECRET_CHANNEL, VOICECHAT_SECRET_CHANNEL,
};

// mod plugin_channels;
mod plugin_message;
mod respawn;
mod secret;
// mod shutdown;
// mod voice;

const MINECRAFT_NAMESPACE: &str = "minecraft";
const MINECRAFT_BRAND_CHANNEL: &str = resource_location!(MINECRAFT_NAMESPACE, "brand");

const VOICECHAT_COMPAT_VERSION: i32 = 15;

#[tokio::main]
async fn main() {
    env_logger::init();
    let account = Account::offline("Raqbot");

    ClientBuilder::new()
        .set_handler(handle)
        .add_plugin(respawn::Plugin)
        // .add_plugin(plugin_channels::Plugin::require_plugins(vec![
        //     VOICECHAT_REQUEST_SECRET_CHANNEL,
        //     VOICECHAT_SECRET_CHANNEL
        // ]))
        // .add_plugin(shutdown::Plugin::default())
        .start(account, "localhost:25565")
        .await
        .unwrap_or_else(|e| println!("Could not start bot: {}", e));
}

struct VoiceSettings {
    secret: uuid::Uuid,
    player: uuid::Uuid,
    host: String,
    port: i32,
    groups_enabled: bool,
}

impl From<SecretResponse> for VoiceSettings {
    fn from(resp: SecretResponse) -> Self {
        return Self {
            secret: resp.secret,
            player: resp.player,
            host: resp.voice_host,
            port: resp.port,
            groups_enabled: resp.groups_enabled,
        };
    }
}

#[derive(Default, Clone, Component)]
pub struct State {
    voice_settings: Arc<RwLock<Option<VoiceSettings>>>,
}

async fn handle(client: Client, event: Event, state: State) -> anyhow::Result<()> {
    match event {
        Event::Chat(m) => {
            info!("{}", m.message().to_ansi());
        }
        Event::Packet(packet) => {
            handle_packet(client, state, packet.deref()).await;
        }
        _ => {}
    }
    Ok(())
}

async fn handle_packet(client: Client, state: State, pkt: &ClientboundGamePacket) {
    if let ClientboundGamePacket::CustomPayload(packet) = pkt {
        match packet.identifier.to_string().as_str() {
            MINECRAFT_BRAND_CHANNEL => {
                match client
                    .write_plugin_message(
                        VOICECHAT_REQUEST_SECRET_CHANNEL,
                        SecretRequest {
                            compat_version: VOICECHAT_COMPAT_VERSION,
                        },
                    )
                    .await
                {
                    Ok(_) => info!("Sent secret request"),
                    Err(e) => error!("Could not send secret request: {}", e),
                }
            }
            VOICECHAT_SECRET_CHANNEL => {
                match SecretResponse::read_from(&mut Cursor::new(&*packet.data)) {
                    Ok(resp) => {
                        state
                            .voice_settings
                            .write()
                            .expect("could not write voice settings")
                            .replace(resp.into());
                        info!("Received voice secret & settings");
                    }
                    Err(e) => error!("Could not parse secret response: {}", e),
                }
            }
            _ => {}
        }
    }
}
