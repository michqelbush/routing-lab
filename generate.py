#!/usr/bin/env python3
"""Build one FRR config for each router from inventory.yml."""
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).parent


def main():
    routers = yaml.safe_load((ROOT / "inventory.yml").read_text())["routers"]
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,  # a typo in the template throws error instead of just printing blank
    )
    template = env.get_template("frr.conf.j2")
    (ROOT / "configs").mkdir(exist_ok=True)

    for name, router in routers.items():
        # Routers that have the same ASN are one site
        site = [r for r in routers.values() if r["asn"] == router["asn"]]
        router["ibgp_peers"] = [r["loopback"] for r in site if r is not router]
        router["advertise"] = [f"{r['loopback']}/32" for r in site]

        (ROOT / "configs" / f"{name}.conf").write_text(template.render(**router))
        print(f"wrote configs/{name}.conf")


if __name__ == "__main__":
    main()
