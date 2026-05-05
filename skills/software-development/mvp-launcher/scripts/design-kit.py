#!/usr/bin/env python3
"""
Design Kit Generator - Create brand identity and design mockups.
Runs after domain registration, before website development.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime

def analyze_brand(prd_content, domain):
    """Analyze PRD to extract brand positioning."""
    print("\n" + "="*60)
    print("🎨 BRAND ANALYSIS")
    print("="*60)
    
    lines = prd_content.split('\n')
    title = lines[0].replace('#', '').strip() if lines else "Project"
    
    keywords = {
        'modern': ['modern', 'sleek', 'minimal', 'clean', 'contemporary'],
        'professional': ['professional', 'business', 'corporate', 'enterprise'],
        'friendly': ['friendly', 'warm', 'welcoming', 'community'],
        'luxury': ['luxury', 'premium', 'elegant', 'sophisticated'],
        'tech': ['tech', 'innovation', 'digital', 'ai', 'startup'],
        'playful': ['fun', 'playful', 'creative', 'colorful', 'bold'],
    }
    
    prd_lower = prd_content.lower()
    brand_traits = []
    
    for trait, words in keywords.items():
        if any(word in prd_lower for word in words):
            brand_traits.append(trait)
    
    if not brand_traits:
        brand_traits = ['modern', 'professional']
    
    print(f"Project: {title}")
    print(f"Domain: {domain}")
    print(f"Brand traits: {', '.join(brand_traits)}")
    
    return {'title': title, 'domain': domain, 'brand_traits': brand_traits}

def generate_design_brief(brand_info):
    """Create design brief with colors and typography."""
    print("\n" + "="*60)
    print("📝 DESIGN BRIEF")
    print("="*60)
    
    traits = brand_info['brand_traits']
    
    color_palettes = {
        'modern': {'primary': '#2563eb', 'secondary': '#64748b', 'accent': '#06b6d4'},
        'professional': {'primary': '#1e40af', 'secondary': '#475569', 'accent': '#f59e0b'},
        'friendly': {'primary': '#ea580c', 'secondary': '#65a30d', 'accent': '#fbbf24'},
        'luxury': {'primary': '#1c1917', 'secondary': '#78716c', 'accent': '#d4af37'},
        'tech': {'primary': '#7c3aed', 'secondary': '#0f172a', 'accent': '#22d3ee'},
        'playful': {'primary': '#db2777', 'secondary': '#7c3aed', 'accent': '#facc15'},
    }
    
    colors = color_palettes.get(traits[0], color_palettes['modern'])
    
    design_brief = {
        'brand_name': brand_info['title'],
        'domain': brand_info['domain'],
        'brand_traits': traits,
        'color_palette': colors,
        'typography': {
            'heading': 'Montserrat' if 'tech' in traits else 'Playfair Display',
            'body': 'Inter'
        },
        'design_principles': [
            'Clean and minimal layouts',
            'High-quality imagery',
            'Consistent spacing',
            'Strong visual hierarchy',
        ],
        'created_at': datetime.now().isoformat(),
    }
    
    print(f"Colors: {colors}")
    print(f"Fonts: {design_brief['typography']}")
    
    return design_brief

def create_logo_prompts(brand_info, project_dir):
    """Generate 5 logo prompts for Nano Banana Pro."""
    print("\n" + "="*60)
    print("🎨 LOGO CONCEPTS (5 variations)")
    print("="*60)
    
    logo_dir = project_dir / 'design' / 'logos'
    logo_dir.mkdir(parents=True, exist_ok=True)
    
    title = brand_info['title']
    traits = brand_info['brand_traits']
    
    prompts = [
        f"Modern minimalist logo for '{title}', clean geometric shapes, {traits[0]} style, vector art, white background",
        f"Abstract wordmark logo for '{title}', flowing curves, {traits[0]} aesthetic, elegant typography, white background",
        f"Icon-based logo for '{title}', symbolic mark, {traits[0]} feel, simple bold icon, white background",
        f"Badge/crest style logo for '{title}', enclosed design, {traits[0]} vibe, professional emblem, white background",
        f"Lettermark logo for '{title}', stylized initials, modern geometric, {traits[0]} style, white background",
    ]
    
    logos = []
    for i, prompt in enumerate(prompts, 1):
        prompt_file = logo_dir / f"logo_{i}_prompt.txt"
        prompt_file.write_text(prompt)
        logos.append({'id': i, 'prompt': prompt})
        print(f"   Logo {i}: {prompt[:50]}...")
    
    print(f"\n✅ {len(logos)} logo prompts ready for Nano Banana Pro")
    return logos

def create_mockup_prompts(brand_info, project_dir):
    """Generate 5 website mockup prompts."""
    print("\n" + "="*60)
    print("🖼️  WEBSITE MOCKUPS (5 variations)")
    print("="*60)
    
    mockup_dir = project_dir / 'design' / 'mockups'
    mockup_dir.mkdir(parents=True, exist_ok=True)
    
    title = brand_info['title']
    traits = brand_info['brand_traits']
    
    prompts = [
        f"Website homepage design for '{title}', hero section with bold headline, {traits[0]} aesthetic, clean layout, desktop view, professional web design, UI/UX",
        f"Website landing page for '{title}', feature showcase section, {traits[0]} style, modern design, desktop mockup, web UI",
        f"Website about page for '{title}', team section with photos, {traits[0]} vibe, elegant layout, desktop view, professional website",
        f"Website services page for '{title}', pricing cards layout, {traits[0]} feel, clean grid, desktop mockup, modern web design",
        f"Website contact page for '{title}', form and map section, {traits[0]} aesthetic, functional design, desktop view, UI design",
    ]
    
    mockups = []
    for i, prompt in enumerate(prompts, 1):
        prompt_file = mockup_dir / f"mockup_{i}_prompt.txt"
        prompt_file.write_text(prompt)
        mockups.append({'id': i, 'prompt': prompt})
        print(f"   Mockup {i}: {prompt[:50]}...")
    
    print(f"\n✅ {len(mockups)} mockup prompts ready for Nano Banana Pro")
    return mockups

def main():
    parser = argparse.ArgumentParser(description='Generate design kit')
    parser.add_argument('--prd', required=True, help='Path to PRD')
    parser.add_argument('--domain', required=True, help='Domain name')
    parser.add_argument('--project-dir', required=True, help='Project directory')
    
    args = parser.parse_args()
    
    prd_content = Path(args.prd).read_text()
    project_dir = Path(args.project_dir)
    
    # Step 1: Brand Analysis
    brand_info = analyze_brand(prd_content, args.domain)
    
    # Step 2: Design Brief
    design_brief = generate_design_brief(brand_info)
    
    # Step 3: Logo Prompts
    logos = create_logo_prompts(brand_info, project_dir)
    
    # Step 4: Mockup Prompts  
    mockups = create_mockup_prompts(brand_info, project_dir)
    
    # Save design kit
    design_kit = {
        'brand_analysis': brand_info,
        'design_brief': design_brief,
        'logos': logos,
        'mockups': mockups,
        'generated_at': datetime.now().isoformat(),
    }
    
    kit_path = project_dir / 'design' / 'design_kit.json'
    kit_path.write_text(json.dumps(design_kit, indent=2))
    
    print("\n" + "="*60)
    print("✅ DESIGN KIT COMPLETE")
    print("="*60)
    print(f"Location: {project_dir / 'design'}")
    print(f"\nNext steps:")
    print(f"1. Use Nano Banana Pro to generate images from prompts")
    print(f"2. Pick your favorite logo (will be converted to SVG)")
    print(f"3. Pick your favorite mockup style")
    print(f"4. Design kit will be provided to coding agent")
    print("="*60)

if __name__ == '__main__':
    main()
