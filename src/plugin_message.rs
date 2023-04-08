use std::error;

use async_trait::async_trait;
use azalea::Client;
use azalea_buf::{McBufWritable, UnsizedByteArray};
use azalea_core::ResourceLocation;
use azalea_protocol::packets::game::serverbound_custom_payload_packet::ServerboundCustomPayloadPacket;
use azalea_protocol::packets::game::ServerboundGamePacket;

#[macro_export]
macro_rules! resource_location {
    ($namespace:expr, $path:expr) => {
        formatcp!("{}:{}", $namespace, $path)
    };
}

#[async_trait]
pub trait ClientPluginMessageExt {
    async fn write_plugin_message(
        self,
        identifier: &str,
        data: impl McBufWritable + Send,
    ) -> Result<(), Box<dyn error::Error>>;
}

#[async_trait]
impl ClientPluginMessageExt for Client {
    async fn write_plugin_message(
        self,
        identifier: &str,
        data: impl McBufWritable + Send,
    ) -> Result<(), Box<dyn error::Error>> {
        let mut buf = Vec::new();
        data.write_into(&mut buf)?;

        let identifier = ResourceLocation::new(identifier);

        let packet = ServerboundCustomPayloadPacket {
            identifier,
            data: UnsizedByteArray::from(buf),
        };
        self.write_packet(ServerboundGamePacket::CustomPayload(packet));
        Ok(())
    }
}
