"""
Test suite for selector manager and fallback system
"""
import pytest
from bs4 import BeautifulSoup
from utils.selector_manager import SelectorManager, SelectorConfig, SelectorStatus, get_selector_manager, initialize_default_selectors


def test_selector_manager_initialization():
    """Test that selector manager initializes correctly"""
    manager = SelectorManager()
    assert manager is not None
    assert manager.selectors == {}


def test_add_selector():
    """Test adding a selector"""
    manager = SelectorManager()
    manager.add_selector('olx', 'title', 'h6[data-cy="listing-title"]', priority=1)
    
    selectors = manager.get_selectors('olx', 'title')
    assert len(selectors) == 1
    assert selectors[0].selector == 'h6[data-cy="listing-title"]'
    assert selectors[0].priority == 1


def test_selector_priority_ordering():
    """Test that selectors are ordered by priority"""
    manager = SelectorManager()
    manager.add_selector('olx', 'title', 'h3', priority=3)
    manager.add_selector('olx', 'title', 'h6', priority=1)
    manager.add_selector('olx', 'title', 'h2', priority=2)
    
    selectors = manager.get_selectors('olx', 'title')
    assert len(selectors) == 3
    assert selectors[0].priority == 1
    assert selectors[1].priority == 2
    assert selectors[2].priority == 3


def test_selector_success_recording():
    """Test recording selector success"""
    config = SelectorConfig(
        selector='h6',
        priority=1,
        source='olx',
        field='title'
    )
    
    assert config.success_count == 0
    assert config.failure_count == 0
    assert config.success_rate == 1.0
    
    config.record_success()
    assert config.success_count == 1
    assert config.success_rate == 1.0


def test_selector_failure_recording():
    """Test recording selector failure"""
    config = SelectorConfig(
        selector='h6',
        priority=1,
        source='olx',
        field='title'
    )
    
    config.record_failure()
    assert config.failure_count == 1
    assert config.success_rate == 0.0
    
    # Record multiple failures to trigger FAILED status
    for _ in range(5):
        config.record_failure()
    
    assert config.status == SelectorStatus.FAILED


def test_extract_with_fallback():
    """Test extraction with fallback selectors"""
    manager = SelectorManager()
    manager.add_selector('olx', 'title', 'h6.missing-class', priority=1)
    manager.add_selector('olx', 'title', 'h2.existing-class', priority=2)
    
    html = '<div><h2 class="existing-class">Test Title</h2></div>'
    soup = BeautifulSoup(html, 'lxml')
    element = soup.find('div')
    
    value, selector_used = manager.extract_with_fallback(element, 'olx', 'title')
    
    assert value == 'Test Title'
    assert selector_used == 'h2.existing-class'


def test_extract_with_fallback_all_fail():
    """Test extraction when all selectors fail"""
    manager = SelectorManager()
    manager.add_selector('olx', 'title', 'h6.missing', priority=1)
    manager.add_selector('olx', 'title', 'h2.missing', priority=2)
    
    html = '<div><p>No title here</p></div>'
    soup = BeautifulSoup(html, 'lxml')
    element = soup.find('div')
    
    value, selector_used = manager.extract_with_fallback(element, 'olx', 'title', default='N/A')
    
    assert value == 'N/A'
    assert selector_used is None


def test_initialize_default_selectors():
    """Test initialization of default selectors"""
    initialize_default_selectors()
    manager = get_selector_manager()
    
    # Check OLX selectors
    olx_title_selectors = manager.get_selectors('olx', 'title')
    assert len(olx_title_selectors) >= 3
    
    # Check Standvirtual selectors
    sv_title_selectors = manager.get_selectors('standvirtual', 'title')
    assert len(sv_title_selectors) >= 3
    
    # Check AutoSapo selectors
    as_title_selectors = manager.get_selectors('autosapo', 'title')
    assert len(as_title_selectors) >= 3


def test_selector_stats():
    """Test getting selector statistics"""
    manager = SelectorManager()
    manager.add_selector('olx', 'title', 'h6', priority=1)
    manager.add_selector('olx', 'title', 'h2', priority=2)
    
    stats = manager.get_selector_stats('olx', 'title')
    
    assert 'total_selectors' in stats
    assert stats['total_selectors'] == 2
    assert 'active' in stats
    assert 'selectors' in stats


def test_selector_testing():
    """Test selector testing functionality"""
    manager = SelectorManager()
    manager.add_selector('olx', 'title', 'h6.test-class', priority=1)
    
    html = '<div><h6 class="test-class">Test</h6></div>'
    
    result = manager.test_selector(html, 'olx', 'title', 'h6.test-class')
    assert result is True
    
    result = manager.test_selector(html, 'olx', 'title', 'h6.missing-class')
    assert result is False


def test_html_caching():
    """Test HTML sample caching"""
    manager = SelectorManager()
    html = '<div>Test HTML</div>'
    
    cache_key = manager.cache_html_sample('olx', 'title', html)
    assert cache_key is not None
    
    retrieved = manager.get_cached_html(cache_key)
    assert retrieved == html


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
