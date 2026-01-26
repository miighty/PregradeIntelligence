#!/usr/bin/env python3
"""
Manual verification script for card identity detection.

Usage:
    python scripts/test_card.py <image_path>
    python scripts/test_card.py <image_path> <image_path2> ...
    python scripts/test_card.py path/to/cards/*.jpg

Examples:
    python scripts/test_card.py ~/Downloads/charizard.jpg
    python scripts/test_card.py card1.png card2.png card3.png
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.card_identity import extract_card_identity_from_path


def test_image(image_path: str) -> None:
    """Test card identity extraction on a single image."""
    print(f"\n{'='*60}")
    print(f"Image: {image_path}")
    print('='*60)
    
    if not os.path.exists(image_path):
        print(f"ERROR: File not found: {image_path}")
        return
    
    result = extract_card_identity_from_path(image_path)
    
    print(f"\nCard Name:    {result.card_name or '(not detected)'}")
    print(f"Set Name:     {result.set_name}")
    print(f"Card Number:  {result.card_number or '(not detected)'}")
    print(f"Variant:      {result.variant or '(none)'}")
    print(f"Confidence:   {result.confidence:.2f}")
    print(f"Match Method: {result.match_method}")
    
    print(f"\nJSON Output:")
    print(json.dumps(result.to_dict(), indent=2))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nNo image path provided.")
        print("Usage: python scripts/test_card.py <image_path>")
        sys.exit(1)
    
    image_paths = sys.argv[1:]
    
    for path in image_paths:
        test_image(path)
    
    print(f"\n{'='*60}")
    print(f"Tested {len(image_paths)} image(s)")
    print('='*60)


if __name__ == '__main__':
    main()
