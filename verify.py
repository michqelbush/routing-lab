#!/usr/bin/env python3

"""Checks that every OSPF and BGP neighbor in the lab is up.

Who each router should be talking to is worked out from inventory.yml, so it
keeps working when you add routers. It retries for up to 90 seconds, because of the face thatOSPF 
and BGP need some time to come up after a deploy.
"""

import ipaddress
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
TIMEOUT_S = 90
LAB_NAME = yaml.safe_load((ROOT / "lab.clab.yml").read_text())["name"]


def vtysh_json(router, command):
    #Run a show command on a router and return its JSON output as a dict
    try:
        result = subprocess.run(
            ["docker", "exec", f"clab-{LAB_NAME}-{router}", "vtysh", "-c", f"{command} json"],
            capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {}  # router not ready yet,,, counts as down and retries


def expected_neighbors(routers):
    """Work out who each router should be talking to, straight from the inventory."""
    expected = {}
    for name, router in routers.items():
        # OSPF: any router with an OSPF link in the same subnet. Neighbors are listed by router ID (loopback)
        ospf = set()
        for link in router["ospf_links"]:
            subnet = ipaddress.ip_interface(link["address"]).network
            for other_name, other in routers.items():
                if other_name != name and any(
                    ipaddress.ip_interface(l["address"]).network == subnet for l in other["ospf_links"]
                ):
                    ospf.add(other["loopback"])

        # BGP: the far end of the eBGP link, and the other routers in the same site (iBGP)
        bgp = {link["peer"] for link in router["ebgp_links"]}
        bgp |= {o["loopback"] for o in routers.values() if o["asn"] == router["asn"] and o is not router}

        expected[name] = {"ospf": ospf, "bgp": bgp}
    return expected


def check(routers, expected):
    rows = []
    for name in routers:
        ospf = vtysh_json(name, "show ip ospf neighbor").get("neighbors", {})
        for nbr in sorted(expected[name]["ospf"]):
            entry = (ospf.get(nbr) or [{}])[0]
            state = entry.get("converged") or entry.get("nbrState") or "missing"
            rows.append((name, "OSPF", nbr, state, state.startswith("Full")))

        bgp = vtysh_json(name, "show bgp ipv4 unicast summary").get("peers", {})
        for peer in sorted(expected[name]["bgp"]):
            state = bgp.get(peer, {}).get("state", "missing")
            rows.append((name, "BGP", peer, state, state == "Established"))
    return rows


def main():
    routers = yaml.safe_load((ROOT / "inventory.yml").read_text())["routers"]
    expected = expected_neighbors(routers)

    deadline = time.time() + TIMEOUT_S
    while True:
        rows = check(routers, expected)
        if all(ok for *_, ok in rows) or time.time() > deadline:
            break
        time.sleep(5)

    for router, proto, neighbor, state, ok in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {router}  {proto:<4}  {neighbor:<15}  {state}")
    failed = sum(not ok for *_, ok in rows)
    print(f"\n{len(rows) - failed}/{len(rows)} sessions up")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
