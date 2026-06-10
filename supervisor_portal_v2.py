from __future__ import annotations

from unified_platform_v2 import apply_style, header, render_supervisor
from backend_engine_v2 import seed_demo_data


def main() -> None:
    apply_style()
    seed_demo_data()
    header()
    render_supervisor()


if __name__ == "__main__":
    main()
