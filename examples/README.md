# Example artwork

The PNG files in this folder are original geometric samples created for Team E's development and automated review. They contain no customer artwork or third-party logos.

- `color-badge.png` checks multiple colors and overlapping curved regions.
- `adjacent-regions.png` exposes shared-edge and duplicate-boundary behavior.
- `holes-and-curves.png` checks holes, circles, and rounded shapes.

Regenerate them with:

```powershell
python scripts/create_samples.py
```

For optional university-brand testing, obtain an approved current asset from the [UNC identity downloads](https://identity.unc.edu/resources/downloads/) and follow its usage requirements. Do not commit that asset or customer artwork without permission. Place private test material under `samples/private/`, which Git ignores.
