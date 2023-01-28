use azalea_buf::{McBufReadable, McBufWritable};
use const_format::formatcp;

use crate::resource_location;

const VOICECHAT_NAMESPACE: &str = "voicechat";

pub const VOICECHAT_REQUEST_SECRET_CHANNEL: &str = resource_location!(VOICECHAT_NAMESPACE, "request_secret");
pub const VOICECHAT_SECRET_CHANNEL: &str = resource_location!(VOICECHAT_NAMESPACE, "secret");

#[derive(Clone, Debug, McBufWritable)]
pub struct SecretRequest {
    pub compat_version: i32,
}

#[derive(Clone, Debug, McBufReadable)]
pub struct SecretResponse {
    secret: uuid::Uuid,
    port: i32,
    player: uuid::Uuid,
    codec: u8,
    mtu_size: i32,
    voice_chat_distance: f64,
    keep_alive: i32,
    groups_enabled: bool,
    voice_host: String,
    allow_recording: bool,
}
