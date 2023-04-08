//! Automatically respawn when we die

use async_trait::async_trait;
use azalea::ecs::app::App;
use azalea::ecs::query::Added;
use azalea::ecs::system::Query;
use azalea::entity::{Dead, Local};
use azalea_client::LocalPlayer;
use azalea_protocol::packets::game::serverbound_client_command_packet::{
    Action, ServerboundClientCommandPacket,
};
use azalea_protocol::packets::game::ServerboundGamePacket;

pub struct Plugin;

#[async_trait]
impl azalea_ecs::app::Plugin for Plugin {
    fn build(&self, app: &mut App) {
        app.add_system(respawn_listener);
    }
}

fn respawn_listener(mut query: Query<&mut LocalPlayer, Added<Dead>>) {
    if let Ok(mut player) = query.get_single_mut() {
        player.write_packet(ServerboundGamePacket::ClientCommand(
            ServerboundClientCommandPacket {
                action: Action::PerformRespawn,
            },
        ))
    }
}
