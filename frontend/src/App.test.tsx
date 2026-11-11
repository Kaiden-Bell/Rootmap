import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";
import { HostTable } from "./App";

type Host = ComponentProps<typeof HostTable>["hosts"][number];

const webHost: Host = {
    id: 1,
    hostname: "web-01",
    ip: "10.0.0.5",
    operating_system: "Ubuntu",
    os_release: "20.04",
    subnet_mask: 24,
    collection_interval: 60,
    is_active: true,
    ssh_port: 22,
};

const dbHost: Host = {
    ...webHost,
    id: 2,
    hostname: "db-01",
    ip: "10.0.0.6",
    subnet_mask: null, 
    is_active: false,
};

describe("HostTable", () => {
    it ("Displays a row for each host, with Yes/No for active", () => {
        render(<HostTable hosts={[webHost, dbHost]} />);
        
        expect(screen.getByText("web-01")).toBeTruthy();
        expect(screen.getByText("db-01")).toBeTruthy();
        expect(screen.getByText("Yes")).toBeTruthy();
        expect(screen.getByText("No")).toBeTruthy();
    });
});