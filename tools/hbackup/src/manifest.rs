use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct Manifest {
    pub timestamp: String,
    pub hostname: String,
    pub file_count: usize,
    pub total_size_bytes: u64,
    pub files: Vec<ManifestEntry>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ManifestEntry {
    pub path: String,
    pub size: u64,
}

impl Manifest {
    pub fn new(timestamp: String, hostname: String) -> Self {
        Self {
            timestamp,
            hostname,
            file_count: 0,
            total_size_bytes: 0,
            files: Vec::new(),
        }
    }

    pub fn add_file(&mut self, path: String, size: u64) {
        self.files.push(ManifestEntry { path, size });
        self.file_count += 1;
        self.total_size_bytes += size;
    }
}
