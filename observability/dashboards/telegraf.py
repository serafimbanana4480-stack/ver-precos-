"""
Telegraf configuration for AutoDeal IA Hunter.
"""
from typing import Dict, List


class TelegrafConfig:
    """Telegraf configuration for metrics collection."""
    
    def __init__(self):
        self.inputs: List[Dict[str, any]] = []
        self.outputs: List[Dict[str, any]] = []
    
    def add_input(self, input_config: Dict[str, any]) -> None:
        """Add input plugin."""
        self.inputs.append(input_config)
    
    def add_output(self, output_config: Dict[str, any]) -> None:
        """Add output plugin."""
        self.outputs.append(output_config)
    
    def get_config(self) -> Dict[str, any]:
        """Get complete Telegraf configuration."""
        return {
            "agent": {
                "interval": "10s",
                "flush_interval": "10s",
            },
            "inputs": self.inputs,
            "outputs": self.outputs,
        }
