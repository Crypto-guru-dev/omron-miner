from __future__ import annotations
import os
import tempfile
import uuid
from pathlib import Path

import bittensor as bt
from dataclasses import dataclass, field
from utils.system import get_temp_folder

# Use RAM disk for temp files if available, otherwise use system temp
TEMP_BASE_DIR = "/dev/shm" if os.path.exists("/dev/shm") else tempfile.gettempdir()

dir_path = os.path.dirname(os.path.realpath(__file__))


@dataclass
class SessionStorage:
    """
    Manages storage for session-related files.
    Optimized for high-performance file I/O operations.
    """

    model_id: str
    session_uuid: str
    base_path: str = field(default_factory=get_temp_folder)
    input_path: str = field(init=False)
    witness_path: str = field(init=False)
    proof_path: str = field(init=False)
    aggregated_proof_path: str = field(init=False)
    public_path: str = field(init=False)

    def __post_init__(self):
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)
        self.input_path = os.path.join(
            self.base_path, f"input_{self.model_id}_{self.session_uuid}.json"
        )
        self.witness_path = os.path.join(
            self.base_path, f"witness_{self.model_id}_{self.session_uuid}.json"
        )
        self.proof_path = os.path.join(
            self.base_path, f"proof_{self.model_id}_{self.session_uuid}.json"
        )
        self.aggregated_proof_path = os.path.join(
            self.base_path, f"aggregated_proof_{self.model_id}_{self.session_uuid}.json"
        )
        self.public_path = os.path.join(
            self.base_path, f"proof_{self.model_id}_{self.session_uuid}.public.json"
        )
        bt.logging.debug(
            f"SessionStorage initialized with model_id: {self.model_id} and session_uuid: {self.session_uuid}"
        )
        bt.logging.trace(f"Input path: {self.input_path}")
        bt.logging.trace(f"Witness path: {self.witness_path}")
        bt.logging.trace(f"Proof path: {self.proof_path}")
        bt.logging.trace(f"Aggregated proof path: {self.aggregated_proof_path}")

    def get_proof_path_for_iteration(self, iteration: int) -> str:
        return os.path.join(
            self.base_path,
            f"proof_{self.model_id}_{self.session_uuid}_{iteration}.json",
        )

    def get_session_path(self, session_id: str) -> str:
        session_path = os.path.join(self.base_path, session_id)
        if not os.path.exists(session_path):
            os.makedirs(session_path)
        return session_path

    def cleanup_files(self):
        """Optimized file cleanup with error handling."""
        cleaned_count = 0
        for file_path in [self.input_path, self.witness_path, self.proof_path, self.aggregated_proof_path, self.public_path]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned_count += 1
                    bt.logging.debug(f"Cleaned up: {file_path}")
                except OSError as e:
                    bt.logging.warning(f"Failed to remove {file_path}: {e}")
        
        # Clean up base directory if empty
        try:
            if os.path.exists(self.base_path) and not os.listdir(self.base_path):
                os.rmdir(self.base_path)
                bt.logging.debug(f"Removed empty base directory: {self.base_path}")
        except OSError as e:
            bt.logging.debug(f"Could not remove base directory {self.base_path}: {e}")
        
        bt.logging.debug(f"Session cleanup completed: {cleaned_count} files removed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_files()
        return None
