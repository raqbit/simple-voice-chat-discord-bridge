use azalea_buf::{McBufReadable, McBufWritable};
use const_format::formatcp;

use crate::resource_location;

const VOICECHAT_NAMESPACE: &str = "voicechat";

pub const VOICECHAT_REQUEST_SECRET_CHANNEL: &str =
    resource_location!(VOICECHAT_NAMESPACE, "request_secret");
pub const VOICECHAT_SECRET_CHANNEL: &str = resource_location!(VOICECHAT_NAMESPACE, "secret");

#[derive(Clone, Debug, McBufWritable)]
pub struct SecretRequest {
    pub compat_version: i32,
}

#[derive(Clone, Debug, McBufReadable)]
pub struct SecretResponse {
    pub secret: uuid::Uuid,
    pub port: i32,
    pub player: uuid::Uuid,
    pub codec: u8,
    pub mtu_size: i32,
    pub voice_chat_distance: f64,
    pub keep_alive: i32,
    pub groups_enabled: bool,
    pub voice_host: String,
    pub allow_recording: bool,
}
