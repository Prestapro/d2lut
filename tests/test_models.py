"""Tests for models."""

from d2lut.models import MarketPost, ObservedPrice, PriceEstimate
from datetime import datetime


class TestMarketPost:
    """Tests for MarketPost model."""
    
    def test_create_market_post(self):
        """Test creating a MarketPost."""
        post = MarketPost(
            post_id=12345,
            title="WTS Jah Rune",
            body_text="Selling Jah rune for 50fg",
            author="test_user",
            timestamp=datetime.now(),
            url="https://forums.d2jsp.org/topic.php?t=123",
            forum_id=271,
            thread_id=123,
        )
        
        assert post.post_id == 12345
        assert post.title == "WTS Jah Rune"
        assert post.body_text == "Selling Jah rune for 50fg"
        assert post.author == "test_user"
        assert post.thread_category_id is None
    
    def test_market_post_defaults(self):
        """Test MarketPost default values."""
        post = MarketPost()
        
        assert post.post_id is None
        assert post.title == ""
        assert post.body_text == ""
        assert post.author == ""
        assert post.timestamp is None


class TestObservedPrice:
    """Tests for ObservedPrice model."""
    
    def test_create_observed_price(self):
        """Test creating an ObservedPrice."""
        obs = ObservedPrice(
            canonical_item_id="jah",
            variant_key="rune:jah",
            price_fg=50.0,
            confidence=0.8,
            thread_category_id=2,
        )
        
        assert obs.canonical_item_id == "jah"
        assert obs.variant_key == "rune:jah"
        assert obs.price_fg == 50.0
        assert obs.confidence == 0.8
        assert obs.thread_category_id == 2


class TestPriceEstimate:
    """Tests for PriceEstimate model."""
    
    def test_create_price_estimate(self):
        """Test creating a PriceEstimate."""
        est = PriceEstimate(
            variant_key="rune:jah",
            fg=55.0,
            confidence="high",
            n_observations=10,
        )
        
        assert est.variant_key == "rune:jah"
        assert est.fg == 55.0
        assert est.confidence == "high"
        assert est.n_observations == 10
