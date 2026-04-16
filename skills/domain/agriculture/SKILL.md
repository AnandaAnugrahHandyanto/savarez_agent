---
name: agriculture
description: Vietnamese agriculture expertise — crop science, pest management, fertilizer, irrigation, livestock, regional specialization for Vietnam farming.
version: 1.0.0
author: tonyteo
license: MIT
metadata:
  hermes:
    tags: [Agriculture, Vietnamese, Farming, Crop-Science, Livestock, Irrigation]
    related_skills: [find-nearby]
---

# Agriculture — Vietnamese Farming QA

Expert-level Vietnamese agricultural knowledge covering crop science, pest management, fertilizer calculations, irrigation, livestock, and regional specialization.

## When to Use

- User asks about Vietnamese farming practices
- Crop disease diagnosis and treatment
- Fertilizer calculation and recommendations
- Irrigation system comparison
- Livestock management advice
- Regional agriculture consulting (ĐBSCL, Tây Nguyên, etc.)

## Levels

| Level | Focus | Example |
|-------|-------|---------|
| 1 | Basic QA | "pH đất ảnh hưởng hấp thụ dinh dưỡng ra sao?" |
| 2 | Multi-turn Consultation | Farmer describes problem → agent asks clarifying questions |
| 3 | Tool-use Scenarios | Weather lookup + fertilizer calculator + pest database |
| 4 | Farming Simulation | Weekly decisions for 1 hecta rice field |
| 5 | Regional Specialist | Region-specific advice for ĐBSCL, Tây Nguyên, Bắc Bộ |

## Knowledge Base

### Crop Science
- Growth factors: light, temperature, water, soil (pH, nutrients), air (CO2)
- Liebig's law of minimum — one limiting factor caps yield
- Crop rotation benefits: nutrient balance, pest cycle disruption, soil structure
- Soil pH ranges: rice 5.5-6.5, coffee 5-6, pepper 5.5-6.5

### Pest Management (IPM)
1. Cultural — resistant varieties, proper spacing, balanced fertilization
2. Biological — natural enemies (parasitoid wasps, predatory spiders, Beauveria fungi)
3. Mechanical — light traps, pheromone traps
4. Chemical — last resort, biopesticides preferred, economic threshold

### Fertilizer Guide
| Crop | Stage | N (kg/ha) | P₂O₅ (kg/ha) | K₂O (kg/ha) |
|------|-------|-----------|---------------|-------------|
| Rice | Seedling | 15 | 8 | 5 |
| Rice | Tillering | 30 | 0 | 10 |
| Rice | Booting | 20 | 0 | 25 |
| Coffee | Flowering | 50 | 40 | 60 |
| Coffee | Fruiting | 40 | 20 | 80 |
| Pepper | Flowering | 30 | 30 | 40 |

### Irrigation Comparison
| Method | Water Saving | Cost | Best For |
|--------|-------------|------|----------|
| Drip | 40-60% | High | Water-scarce areas, row crops |
| Sprinkler | 20-30% | Medium | General field crops |
| Flood | 0% | Low | Rice paddies |

### Regional Specialization
- **ĐBSCL** — Rice-shrimp rotation, tropical fruits, saline intrusion adaptation
- **Tây Nguyên** — Coffee (Robusta/Arabica), pepper, basaltic soil
- **Bắc Bộ** — Tea, temperate vegetables, seasonal typhoons
- **Đông Nam Bộ** — Rubber, durian, high-tech agriculture

## Consultation Workflow

When a farmer describes a problem:

1. **Ask clarifying questions** (2-3 minimum):
   - Region/location
   - Soil type
   - Growth stage
   - What treatments have been tried
   - Scale of production

2. **Diagnose** using available tools:
   - `weather_lookup` — check local conditions
   - `fertilizer_calculator` — calculate proper doses
   - `pest_database` — match symptoms to diseases
   - `cost_calculator` — estimate economics

3. **Recommend** specific, actionable advice:
   - Exact fertilizer doses with timing
   - Specific pesticide names and dosages
   - Cost estimates and expected yields
   - Timeline for recovery

## Common Diseases Quick Reference

| Crop | Symptom | Likely Cause | Treatment |
|------|---------|-------------|-----------|
| Rice | Yellow leaves | N deficiency or blast | N fertilizer / Tricyclazole |
| Rice | Brown spots | Brown spot disease | Mancozeb spray |
| Coffee | Yellow leaves | Rust or root rot | Copper oxychloride / Metalaxyl |
| Coffee | Low yield | Nutrient imbalance | NPK + micronutrients |
| Pepper | Root rot | Phytophthora | Metalaxyl + Fosetyl-Al, raise beds |
| Shrimp | Sudden death | Water quality (DO/NH3) | Probiotics, reduce density |

## Prime Intellect Evaluation

```bash
prime env install tonyteo/agriculture
prime eval run tonyteo/agriculture -m <model> --env-args '{"level": 1}'
```

## Language

Always respond in Vietnamese (tiếng Việt) when the user asks in Vietnamese. Use technical agricultural terms appropriately.
