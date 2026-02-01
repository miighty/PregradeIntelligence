# Phone dataset capture (front/back)

Folders created:

- `/Users/vr/Documents/cards/phone/front`
- `/Users/vr/Documents/cards/phone/back`

## Capture guidance (quick)

Goal: make identity + gatekeeper robust to real-world capture.

Try to include:
- different desks/backgrounds
- hands visible sometimes
- sleeves and unsleeved
- some glare/reflections
- slight tilt/perspective
- partial cards (a bit out of frame)

Suggested: 100+ fronts, 50+ backs.

## Naming
Any filename is fine. Avoid duplicates.

## After capture
To include these in training, you can either:
- copy into the existing dataset folders (`/Users/vr/Documents/cards/front|back`), or
- change your training data root to point at a combined directory.

Example combine (recommended):

```
/Users/vr/Documents/cards_combined/
  front/  (scans + phone)
  back/
```

Then train using that combined root.
