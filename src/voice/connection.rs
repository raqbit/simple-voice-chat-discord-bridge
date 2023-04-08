use std::{io, result};
use std::fmt::Debug;
use std::net::SocketAddr;

use azalea_protocol::packets::ProtocolPacket;
use cbc::cipher::{Key, KeyIvInit};
use thiserror::Error;
use tokio::net::{ToSocketAddrs, UdpSocket};

#[derive(Error, Debug)]
pub enum ConnectionError {
    #[error("{0}")]
    Io(#[from] io::Error),
    #[error("Write without configured key")]
    WriteWithoutKey,
}

pub type Result<T> = result::Result<T, ConnectionError>;

struct Connection {
    sock: UdpSocket,
    key: Option<Key<cbc::Encryptor<aes::Aes128>>>
}

impl Connection {
    async fn new(address: SocketAddr) -> Result<Self> {
        let sock = UdpSocket::bind(":0").await?;

        sock.connect(address).await?;
        Ok(Self {
            sock,
            key: None,
        })
    }

    async fn set_encryption_key(&mut self, key: [u8; 16]) {
        self.key = Some(key.into());
    }

    async fn write<P: ProtocolPacket + Debug>(&self, packet: P) -> Result<()> {
        if let Some(key) = self.key {
            let cipher = cbc::Encryptor::new(&key, );
            Ok(())
        } else {
            Err(ConnectionError::WriteWithoutKey)
        }
    }
}

pub struct Client {}

impl Client {
    pub async fn connect<A: ToSocketAddrs>(address: impl TryInto<A>) -> Result<()> {
        let conn = Connection::new(address).await?;

        // let mut buf = [0; 4096];

        Ok(())
    }

    async fn send_packet() {}
}
