---
name: fire-danger-assessment
description: Instructions for interpreting McArthur FFDI ratings, danger level meanings, recommended ranger actions, and escalation criteria
allowed-tools:
  - assess_fire_danger
  - get_current_weather
  - get_forecast
---

# Fire Danger Assessment

## McArthur Forest Fire Danger Index (FFDI)

The McArthur FFDI is the standard Australian metric for assessing forest fire danger. It combines temperature, relative humidity, wind speed, and drought factor into a single numeric index. The `assess_fire_danger` tool calculates a simplified FFDI and maps it to one of five danger levels.

### Danger Levels

| Level | FFDI Range | Meaning |
|-------|-----------|---------|
| **low** | 0–5 | Fires unlikely to spread. Normal field operations. |
| **moderate** | 5–12 | Fires may spread slowly. Stay aware of conditions. |
| **high** | 12–25 | Fires spread quickly. Increased vigilance required. |
| **very_high** | 25–50 | Fires spread rapidly and are difficult to control. Restrict activities. |
| **extreme** | 50+ | Catastrophic fire conditions. Evacuate and cease non-emergency operations. |

## Recommended Ranger Actions by Level

### Low
- Normal field operations permitted.
- Routine fire break inspections on schedule.

### Moderate
- Monitor weather forecasts for changes.
- Ensure fire extinguishers and communication equipment are accessible.
- Brief field teams on current conditions.

### High
- Increase vigilance during field patrols.
- Check fire breaks and clear any accumulated debris.
- Ensure all communication equipment is charged and operational.
- Confirm evacuation routes are clear and known to all team members.

### Very High
- Restrict field activities to essential operations only.
- Notify base of your exact location and expected return time.
- Prepare evacuation routes and identify safe refuge points.
- Maintain continuous radio contact with base.
- Postpone non-critical surveys and research activities.

### Extreme
- **Evacuate to designated safe zones immediately.**
- Cease all non-emergency field operations.
- Contact the local fire authority and report your status.
- Follow all directives from emergency services.
- Do not re-enter the field until the danger level drops and clearance is given.

## Escalation Criteria

Escalate to emergency services (Emergency 000) when:

1. Fire danger is assessed as **extreme**.
2. Fire danger is **very_high** and rising, with no forecast improvement.
3. You observe active fire, smoke, or smell burning in the field.
4. Communication with base is lost during **high** or above conditions.

## Using Weather Tools

- Call `get_current_weather` first to understand present conditions.
- Use `get_forecast` to check whether conditions are expected to worsen or improve.
- Call `assess_fire_danger` to get the calculated danger level for the location.
- Always present the danger level alongside the raw weather data so rangers can make informed decisions.
