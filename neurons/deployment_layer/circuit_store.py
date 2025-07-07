from __future__ import annotations

import os
import traceback
import threading
from typing import Optional
from functools import lru_cache

import bittensor as bt
from packaging import version

from constants import IGNORED_MODEL_HASHES, MAINNET_TESTNET_UIDS
from execution_layer.circuit import Circuit

# Global cache for circuit metadata
_circuit_metadata_cache = {}
_metadata_cache_lock = threading.Lock()


class CircuitStore:
    """
    A Singleton class to manage and store Circuit objects.
    Optimized for high-performance circuit loading and caching.

    This class is responsible for loading, storing, and retrieving Circuit objects.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """
        Override the __new__ method to implement the Singleton pattern.
        """
        if not cls._instance:
            cls._instance = super(CircuitStore, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        """
        Initialize the CircuitStore.

        Creates an empty dictionary to store Circuit objects and loads circuits.
        """
        self.circuits: dict[str, Circuit] = {}
        self._load_lock = threading.Lock()

    def load_circuits(self, deployment_layer_path: Optional[str] = None):
        """
        Load circuits from the file system with optimized loading.

        Searches for directories starting with 'model_' in the deployment layer path,
        attempts to create Circuit objects from these directories, and stores them
        in the circuits dictionary.
        """
        deployment_layer_path = os.path.dirname(__file__)
        bt.logging.info(f"Loading circuits from {deployment_layer_path}")

        # Get all model directories first
        model_dirs = []
        for folder_name in os.listdir(deployment_layer_path):
            folder_path = os.path.join(deployment_layer_path, folder_name)
            if os.path.isdir(folder_path) and folder_name.startswith("model_"):
                circuit_id = folder_name.split("_")[1]
                if circuit_id not in IGNORED_MODEL_HASHES:
                    model_dirs.append((circuit_id, folder_path))

        bt.logging.info(f"Found {len(model_dirs)} circuits to load")

        # Load circuits with better error handling
        loaded_count = 0
        for circuit_id, folder_path in model_dirs:
            try:
                bt.logging.debug(f"Loading circuit {circuit_id}")
                
                # Check if circuit is already cached
                if circuit_id in self.circuits:
                    bt.logging.debug(f"Circuit {circuit_id} already loaded, skipping")
                    loaded_count += 1
                    continue
                
                # Load circuit with optimized initialization
                circuit = self._load_circuit_optimized(circuit_id, folder_path)
                if circuit:
                    self.circuits[circuit_id] = circuit
                    loaded_count += 1
                    bt.logging.info(f"Successfully loaded circuit {circuit_id}")
                else:
                    bt.logging.warning(f"Failed to load circuit {circuit_id}")
                    
            except Exception as e:
                bt.logging.error(f"Error loading circuit {circuit_id}: {e}")
                traceback.print_exc()
                continue

        bt.logging.info(f"Loaded {loaded_count}/{len(model_dirs)} circuits successfully")

    def _load_circuit_optimized(self, circuit_id: str, folder_path: str) -> Optional[Circuit]:
        """
        Optimized circuit loading with metadata caching.
        """
        try:
            # Check metadata cache first
            with _metadata_cache_lock:
                if circuit_id in _circuit_metadata_cache:
                    bt.logging.debug(f"Using cached metadata for circuit {circuit_id}")
                    return Circuit(circuit_id, cached_metadata=_circuit_metadata_cache[circuit_id])
            
            # Load circuit normally
            circuit = Circuit(circuit_id)
            
            # Cache metadata for future loads
            with _metadata_cache_lock:
                _circuit_metadata_cache[circuit_id] = circuit.metadata
            
            return circuit
            
        except Exception as e:
            bt.logging.error(f"Failed to load circuit {circuit_id}: {e}")
            return None

    @lru_cache(maxsize=128)
    def get_circuit(self, circuit_id: str) -> Circuit | None:
        """
        Retrieve a Circuit object by its ID with caching.

        Args:
            circuit_id (str): The ID of the circuit to retrieve.

        Returns:
            Circuit | None: The Circuit object if found, None otherwise.
        """
        circuit = self.circuits.get(circuit_id)
        if circuit:
            bt.logging.debug(f"Retrieved circuit {circuit}")
        else:
            bt.logging.warning(f"Circuit {circuit_id} not found")
        return circuit

    def get_latest_circuit_for_netuid(self, netuid: int):
        """
        Get the latest circuit for a given netuid by comparing semver version strings.

        Args:
            netuid (int): The subnet ID to find the latest circuit for

        Returns:
            Circuit | None: The circuit with the highest semver version for the given netuid,
            or None if no circuits found
        """

        matching_circuits = [
            c for c in self.circuits.values() if c.metadata.netuid == netuid
        ]
        if not matching_circuits:
            return None

        return max(matching_circuits, key=lambda c: version.parse(c.metadata.version))

    def get_circuit_for_netuid_and_version(
        self, netuid: int, version: int
    ) -> Circuit | None:
        """
        Get the circuit for a given netuid and version.
        """
        matching_circuits = [
            c
            for c in self.circuits.values()
            if c.metadata.netuid == netuid and c.metadata.weights_version == version
        ]
        if not matching_circuits:
            bt.logging.warning(
                f"No circuit found for netuid {netuid} and weights version {version}"
            )
            return None
        return matching_circuits[0]

    def get_latest_circuit_by_name(self, circuit_name: str) -> Circuit | None:
        """
        Get the latest circuit by name.
        """
        matching_circuits = [
            c for c in self.circuits.values() if c.metadata.name == circuit_name
        ]
        return max(matching_circuits, key=lambda c: version.parse(c.metadata.version))

    def get_circuit_by_name_and_version(
        self, circuit_name: str, version: int
    ) -> Circuit | None:
        """
        Get the circuit by name and version.
        """
        matching_circuits = [
            c
            for c in self.circuits.values()
            if c.metadata.name == circuit_name and c.metadata.version == version
        ]
        return matching_circuits[0] if matching_circuits else None

    def list_circuits(self) -> list[str]:
        """
        Get a list of all circuit IDs.

        Returns:
            list[str]: A list of circuit IDs.
        """
        circuit_list = list(self.circuits.keys())
        bt.logging.debug(f"Listed {len(circuit_list)} circuits")
        return circuit_list

    def list_circuit_metadata(self) -> list[dict]:
        """
        JSON safe circuit metadata for use in API serving.
        """
        data: list[dict] = []
        for circuit in self.circuits.values():
            data.append(
                {
                    "id": circuit.id,
                    "name": circuit.metadata.name,
                    "description": circuit.metadata.description,
                    "author": circuit.metadata.author,
                    "version": circuit.metadata.version,
                    "type": circuit.metadata.type,
                    "proof_system": circuit.metadata.proof_system,
                    "netuid": circuit.metadata.netuid,
                    "testnet_netuids": (
                        [
                            uid[1]
                            for uid in MAINNET_TESTNET_UIDS
                            if uid[0] == int(circuit.metadata.netuid)
                        ]
                        if circuit.metadata.netuid
                        else None
                    ),
                    "weights_version": circuit.metadata.weights_version,
                    "input_schema": circuit.input_handler.schema.model_json_schema(),
                }
            )
        return data

    def clear_cache(self):
        """Clear all caches for memory management."""
        with _metadata_cache_lock:
            _circuit_metadata_cache.clear()
        self.get_circuit.cache_clear()
        bt.logging.info("Circuit store caches cleared")


circuit_store = CircuitStore()
bt.logging.info("Optimized CircuitStore initialized")
