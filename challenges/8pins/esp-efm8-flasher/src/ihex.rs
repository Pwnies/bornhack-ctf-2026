use core::str::FromStr;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct IHexRecord {
    pub length: u8,
    pub address: u16,
    pub record_type: u8,
    pub checksum: u8,
    pub data: heapless::Vec<u8, 256>
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum IHexError {
    ChecksumError,
    LengthError,
    TooShort,
    InvalidCode,
    HexError,
}

impl FromStr for IHexRecord {
    type Err = IHexError;

    fn from_str(s: &str) -> Result<Self, IHexError> {
        let mut s = s.strip_prefix(':').ok_or(IHexError::InvalidCode)?.trim_end_matches(|ch: char| ch.is_whitespace());
        let mut bytes = heapless::Vec::<u8, 270>::new();

        while let Some((hex_byte, rest)) = s.split_at_checked(2) {
            let byte = u8::from_str_radix(hex_byte, 16).map_err(|_| IHexError::HexError)?;
            bytes.push(byte).map_err(|_| IHexError::LengthError)?;
            s = rest;
        }

        let bytes = &bytes[..];

        let (&checksum, bytes) = bytes.split_last().ok_or(IHexError::TooShort)?;

        let mut checksum_computed = 0u8;
        for &byte in bytes {
            checksum_computed = checksum_computed.wrapping_sub(byte);
        }
        if checksum_computed != checksum {
            return Err(IHexError::ChecksumError)
        }

        let (&length, bytes) = bytes.split_first().ok_or(IHexError::TooShort)?;
        let (&address, bytes) = bytes.split_first_chunk::<2>().ok_or(IHexError::TooShort)?;
        let address = u16::from_be_bytes(address);
        let (&record_type, bytes) = bytes.split_first().ok_or(IHexError::TooShort)?;
        let data = heapless::Vec::try_from(bytes).map_err(|_| IHexError::LengthError)?;
        if data.len() != length as usize {
            return Err(IHexError::LengthError);
        }

        Ok(IHexRecord {
            length,
            address,
            record_type,
            checksum,
            data,
        })
    }

}
