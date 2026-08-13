/** @vitest-environment jsdom */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AssistantMessageMetadata } from "./message-metadata";

afterEach(() => {
  cleanup();
});

describe("AssistantMessageMetadata", () => {
  it("renders policy citations under a Sources section", () => {
    render(
      <AssistantMessageMetadata
        sources={["sample_policy.md — Section 1: Home Water Damage Coverage"]}
        toolCalls={[]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Sources" })).not.toBeNull();
    expect(
      screen.getByText("sample_policy.md — Section 1: Home Water Damage Coverage"),
    ).not.toBeNull();
  });

  it("renders successful claim lookup and submission cards from safe fields only", () => {
    render(
      <AssistantMessageMetadata
        sources={[]}
        toolCalls={[
          {
            name: "get_claim_status",
            status: "success",
            arguments: "CLM-9014",
            result_summary: "Claim status: Under Review.",
          },
          {
            name: "submit_claim",
            status: "success",
            arguments: "{\"policy_number\":\"POL-123\",\"amount\":750}",
            result_summary: "Claim submitted. Confirmation ID: CLM-ABCDEF12.",
          },
        ]}
      />,
    );

    expect(screen.getByText("get_claim_status")).not.toBeNull();
    expect(screen.getByText("submit_claim")).not.toBeNull();
    expect(screen.getByText("Claim status: Under Review.")).not.toBeNull();
    expect(screen.getByText("Claim submitted. Confirmation ID: CLM-ABCDEF12.")).not.toBeNull();
    expect(screen.getAllByText("Completed")).toHaveLength(2);
    expect(screen.queryByText(/policy_number/)).toBeNull();
    expect(screen.queryByText(/750/)).toBeNull();
  });

  it("visually distinguishes failed tool activity and keeps the failure readable", () => {
    render(
      <AssistantMessageMetadata
        sources={[]}
        toolCalls={[
          {
            name: "search_policy",
            status: "failure",
            arguments: "hidden internal query",
            result_summary: "Policy search could not be completed safely.",
          },
        ]}
      />,
    );

    const card = screen.getByText("search_policy").closest("article");
    expect(card?.getAttribute("data-status")).toBe("failure");
    expect(screen.getByText("Not completed")).not.toBeNull();
    expect(screen.getByText("Policy search could not be completed safely.")).not.toBeNull();
    expect(screen.queryByText("hidden internal query")).toBeNull();
  });

  it("renders no metadata container for an empty source and tool-call set", () => {
    const { container } = render(<AssistantMessageMetadata sources={[]} toolCalls={[]} />);

    expect(container.firstChild).toBeNull();
    expect(screen.queryByRole("heading", { name: "Sources" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Tool activity" })).toBeNull();
  });
});
