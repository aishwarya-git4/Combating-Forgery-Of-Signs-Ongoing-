import hashlib
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

# Simulated storage
chunk_store = {}  # Chunk Hash -> Chunk Data
metadata_store = {}  # CID -> List of Chunk Hashes

CHUNK_SIZE = 4096  # 4KB chunks

def compute_hash(data):
    """Computes SHA-256 hash of the given data."""
    return hashlib.sha256(data).hexdigest()

def store_file(file_path):
    """Stores a file with deduplication and returns its CID."""
    file_chunks = []
    
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            chunk_hash = compute_hash(chunk)
            file_chunks.append(chunk_hash)
            
            # Store chunk only if not already stored
            if chunk_hash not in chunk_store:
                chunk_store[chunk_hash] = chunk

    # Generate a unique CID based on file's chunk hashes
    file_cid = compute_hash("".join(file_chunks).encode())

    # Store metadata
    metadata_store[file_cid] = file_chunks
    return file_cid

def retrieve_file(cid, output_path):
    """Reconstructs the file using CID and writes it to output_path."""
    if cid not in metadata_store:
        raise FileNotFoundError("File not found!")

    chunk_hashes = metadata_store[cid]

    # Parallel retrieval of chunks
    def fetch_chunk(chunk_hash):
        return chunk_store[chunk_hash]

    with ThreadPoolExecutor() as executor:
        chunks = list(executor.map(fetch_chunk, chunk_hashes))

    # Write the reconstructed file
    with open(output_path, "wb") as f:
        for chunk in chunks:
            f.write(chunk)

# Example Usage
file_cid = store_file("sample.txt")
print(f"Stored file CID: {file_cid}")

retrieve_file(file_cid, "reconstructed_sample.txt")
print("File retrieved successfully.")


