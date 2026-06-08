"""
HTML Structure Change Detection and Fingerprinting
Detects changes in HTML structure to alert on potential scraper breakage
"""
from __future__ import annotations
import logging
import hashlib
import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class HTMLStructureFingerprint:
    """Fingerprint of HTML structure"""
    hash: str
    timestamp: datetime
    source: str
    structure_signature: str
    element_count: int
    depth: int
    tag_distribution: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hash': self.hash,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'structure_signature': self.structure_signature,
            'element_count': self.element_count,
            'depth': self.depth,
            'tag_distribution': self.tag_distribution
        }


@dataclass
class ChangeEvent:
    """Represents a detected HTML structure change"""
    old_fingerprint: HTMLStructureFingerprint
    new_fingerprint: HTMLStructureFingerprint
    change_type: str  # 'minor', 'moderate', 'major'
    detected_at: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'old_hash': self.old_fingerprint.hash,
            'new_hash': self.new_fingerprint.hash,
            'change_type': self.change_type,
            'detected_at': self.detected_at.isoformat(),
            'details': self.details
        }


class HTMLChangeDetector:
    """Detects changes in HTML structure over time"""
    
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path("./data/html_fingerprints")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.fingerprints: Dict[str, List[HTMLStructureFingerprint]] = defaultdict(list)
        self.change_history: List[ChangeEvent] = []
        self.alert_threshold = 0.3  # 30% change considered significant
        
        # Load existing fingerprints
        self._load_fingerprints()
    
    def generate_fingerprint(self, html: str, source: str) -> HTMLStructureFingerprint:
        """
        Generate a fingerprint of HTML structure
        
        Args:
            html: HTML content
            source: Source identifier (e.g., 'olx', 'standvirtual')
            
        Returns:
            HTMLStructureFingerprint object
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("BeautifulSoup is required for HTML fingerprinting")
        
        soup = BeautifulSoup(html, 'lxml')
        
        # Calculate structure signature (simplified DOM structure)
        structure_signature = self._calculate_structure_signature(soup)
        
        # Count elements
        element_count = len(soup.find_all())
        
        # Calculate depth
        depth = self._calculate_depth(soup)
        
        # Count tag distribution
        tag_distribution = self._count_tags(soup)
        
        # Generate hash
        hash_input = f"{structure_signature}:{element_count}:{depth}:{json.dumps(tag_distribution, sort_keys=True)}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()
        
        fingerprint = HTMLStructureFingerprint(
            hash=hash_value,
            timestamp=datetime.now(timezone.utc),
            source=source,
            structure_signature=structure_signature,
            element_count=element_count,
            depth=depth,
            tag_distribution=tag_distribution
        )
        
        return fingerprint
    
    def _calculate_structure_signature(self, soup) -> str:
        """Calculate a simplified structure signature"""
        # Get the tag hierarchy (first 3 levels)
        root = soup.find()
        if not root:
            return "empty"
        
        signature = []
        self._build_signature(root, signature, max_depth=3)
        return "|".join(signature)
    
    def _build_signature(self, element, signature: List[str], current_depth: int = 0, max_depth: int = 3) -> None:
        """Recursively build structure signature"""
        if current_depth >= max_depth or not element:
            return

        tag = element.name if element.name else "text"
        signature.append(tag)

        # Add first 3 children (only elements with children attribute)
        if hasattr(element, 'children'):
            children = list(element.children)[:3]
            for child in children:
                if hasattr(child, 'name'):
                    self._build_signature(child, signature, current_depth + 1, max_depth)
    
    def _calculate_depth(self, soup) -> int:
        """Calculate maximum depth of DOM tree"""
        def get_depth(elem, current=0):
            if not elem or not hasattr(elem, 'children'):
                return current
            children = [c for c in elem.children if hasattr(c, 'name')]
            if not children:
                return current
            return max(get_depth(c, current + 1) for c in children)
        
        root = soup.find()
        return get_depth(root) if root else 0
    
    def _count_tags(self, soup) -> Dict[str, int]:
        """Count occurrences of each tag"""
        tag_counts = defaultdict(int)
        for element in soup.find_all():
            if element.name:
                tag_counts[element.name] += 1
        return dict(tag_counts)
    
    def has_changed(self, html_a: str, html_b: str, source: str = "unknown") -> bool:
        """Return True if two HTML blobs differ structurally (legacy/test API)."""
        fp_a = self.generate_fingerprint(html_a, source)
        fp_b = self.generate_fingerprint(html_b, source)
        return fp_a.hash != fp_b.hash

    def detect_change(
        self,
        html: str,
        source: str,
        store_sample: bool = True
    ) -> Tuple[Optional[ChangeEvent], HTMLStructureFingerprint]:
        """
        Detect if HTML structure has changed
        
        Args:
            html: HTML content
            source: Source identifier
            store_sample: Whether to store HTML sample
            
        Returns:
            Tuple of (ChangeEvent if change detected, new_fingerprint)
        """
        new_fingerprint = self.generate_fingerprint(html, source)
        
        # Get previous fingerprints for this source
        previous = self.fingerprints.get(source, [])
        
        if not previous:
            # First time seeing this source
            self.fingerprints[source].append(new_fingerprint)
            self._store_fingerprint(new_fingerprint, html if store_sample else None)
            return None, new_fingerprint
        
        # Compare with most recent fingerprint
        last_fingerprint = previous[-1]
        
        if last_fingerprint.hash == new_fingerprint.hash:
            # No change
            logger.debug(f"No structural change detected for {source}")
            return None, new_fingerprint
        
        # Calculate change severity
        change_event = self._calculate_change_severity(last_fingerprint, new_fingerprint)
        
        # Store new fingerprint
        self.fingerprints[source].append(new_fingerprint)
        self._store_fingerprint(new_fingerprint, html if store_sample else None)
        self.change_history.append(change_event)
        
        # Alert on significant changes
        if change_event.change_type in ['moderate', 'major']:
            self._send_alert(change_event)
        
        return change_event, new_fingerprint
    
    def _calculate_change_severity(
        self,
        old: HTMLStructureFingerprint,
        new: HTMLStructureFingerprint
    ) -> ChangeEvent:
        """Calculate severity of structural change"""
        details = {}
        
        # Compare element count
        element_diff = abs(new.element_count - old.element_count)
        element_change_pct = element_diff / max(old.element_count, 1)
        
        # Compare depth
        depth_diff = abs(new.depth - old.depth)
        
        # Compare tag distribution
        tag_similarity = self._compare_tag_distribution(old.tag_distribution, new.tag_distribution)
        
        # Compare structure signature
        signature_changed = old.structure_signature != new.structure_signature
        
        details.update({
            'element_count_diff': element_diff,
            'element_change_pct': element_change_pct,
            'depth_diff': depth_diff,
            'tag_similarity': tag_similarity,
            'signature_changed': signature_changed
        })
        
        # Determine change type
        if signature_changed and tag_similarity < 0.5:
            change_type = 'major'
        elif element_change_pct > 0.3 or tag_similarity < 0.7:
            change_type = 'moderate'
        else:
            change_type = 'minor'
        
        return ChangeEvent(
            old_fingerprint=old,
            new_fingerprint=new,
            change_type=change_type,
            detected_at=datetime.now(timezone.utc),
            details=details
        )
    
    def _compare_tag_distribution(
        self,
        old_dist: Dict[str, int],
        new_dist: Dict[str, int]
    ) -> float:
        """Calculate similarity between tag distributions (0-1 scale)"""
        all_tags = set(old_dist.keys()) | set(new_dist.keys())
        
        if not all_tags:
            return 1.0
        
        similarity_sum = 0
        for tag in all_tags:
            old_count = old_dist.get(tag, 0)
            new_count = new_dist.get(tag, 0)
            max_count = max(old_count, new_count, 1)
            
            if old_count == new_count:
                similarity_sum += 1.0
            else:
                similarity_sum += 1.0 - (abs(old_count - new_count) / max_count)
        
        return similarity_sum / len(all_tags)
    
    def _send_alert(self, change_event: ChangeEvent) -> None:
        """Send alert for significant HTML structure changes"""
        logger.warning(
            f"HTML STRUCTURE CHANGE DETECTED: {change_event.new_fingerprint.source}\n"
            f"Change Type: {change_event.change_type}\n"
            f"Old Hash: {change_event.old_fingerprint.hash}\n"
            f"New Hash: {change_event.new_fingerprint.hash}\n"
            f"Details: {json.dumps(change_event.details, indent=2)}"
        )
        
        # TODO: Integrate with notification channels (Discord, Email, etc.)
    
    def _store_fingerprint(self, fingerprint: HTMLStructureFingerprint, html_sample: Optional[str] = None) -> None:
        """Store fingerprint and optionally HTML sample"""
        # Store fingerprint metadata
        fingerprint_file = self.storage_dir / f"{fingerprint.source}_fingerprints.json"
        
        fingerprints_data = []
        if fingerprint_file.exists():
            try:
                with open(fingerprint_file, 'r') as f:
                    fingerprints_data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading fingerprints: {e}")
        
        fingerprints_data.append(fingerprint.to_dict())
        
        # Keep only last 100 fingerprints per source
        if len(fingerprints_data) > 100:
            fingerprints_data = fingerprints_data[-100:]
        
        with open(fingerprint_file, 'w') as f:
            json.dump(fingerprints_data, f, indent=2)
        
        # Store HTML sample if provided
        if html_sample:
            sample_file = self.storage_dir / f"{fingerprint.hash[:16]}.html"
            with open(sample_file, 'w', encoding='utf-8') as f:
                f.write(html_sample)
    
    def _load_fingerprints(self) -> None:
        """Load existing fingerprints from storage"""
        for file in self.storage_dir.glob("*_fingerprints.json"):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                
                for fp_data in data:
                    fingerprint = HTMLStructureFingerprint(
                        hash=fp_data['hash'],
                        timestamp=datetime.fromisoformat(fp_data['timestamp']),
                        source=fp_data['source'],
                        structure_signature=fp_data['structure_signature'],
                        element_count=fp_data['element_count'],
                        depth=fp_data['depth'],
                        tag_distribution=fp_data['tag_distribution']
                    )
                    self.fingerprints[fingerprint.source].append(fingerprint)
                
                logger.info(f"Loaded {len(data)} fingerprints from {file.name}")
            except Exception as e:
                logger.error(f"Error loading fingerprints from {file.name}: {e}")
    
    def get_change_history(self, source: Optional[str] = None, hours: int = 24) -> List[ChangeEvent]:
        """Get change history for a source or all sources"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        if source:
            return [
                ce for ce in self.change_history
                if ce.new_fingerprint.source == source and ce.detected_at >= cutoff
            ]
        else:
            return [ce for ce in self.change_history if ce.detected_at >= cutoff]
    
    def get_fingerprint_history(self, source: str, count: int = 10) -> List[HTMLStructureFingerprint]:
        """Get fingerprint history for a source"""
        return self.fingerprints.get(source, [])[-count:]


# Global HTML change detector instance
_html_change_detector = HTMLChangeDetector()


def get_html_change_detector() -> HTMLChangeDetector:
    """Get the global HTML change detector instance"""
    return _html_change_detector
