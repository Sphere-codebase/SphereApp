import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import ChatStatusHud from "@/components/chat/ChatStatusHud";

const okResponse = (body: object) =>
  Promise.resolve(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    })
  );

const htmlResponse = (html: string) =>
  Promise.resolve(
    new Response(html, {
      status: 200,
      headers: { "content-type": "text/html" },
    })
  );

afterEach(() => {
  vi.unstubAllGlobals();
});

test("renders three status lamps", async () => {
  const fetchMock = vi.fn(() =>
    okResponse({ ok: true, checks: { db: "ok", llm: "ok" } })
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<ChatStatusHud busy={false} />);

  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  expect(await screen.findByLabelText("API status Active")).toBeInTheDocument();
  expect(await screen.findByLabelText("DB status Active")).toBeInTheDocument();
  expect(await screen.findByLabelText("LLM status Active")).toBeInTheDocument();
  expect(screen.getByTestId("lamp-llm-dot").className).toContain("bg-emerald-500");
});

test("shows legend when info icon is clicked", async () => {
  const fetchMock = vi.fn(() =>
    okResponse({ ok: true, checks: { db: "ok", llm: "ok" } })
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<ChatStatusHud busy={false} />);

  const button = screen.getByLabelText("Status legend");
  await userEvent.click(button);
  expect(screen.getByText("Legend")).toBeInTheDocument();
  expect(screen.getByText("Green")).toBeInTheDocument();
});

test("blinks the LLM lamp while busy", async () => {
  const fetchMock = vi.fn(() =>
    okResponse({ ok: true, checks: { db: "ok", llm: "ok" } })
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<ChatStatusHud busy />);

  const llmLamp = await screen.findByTestId("lamp-llm-dot");
  await waitFor(() => expect(llmLamp.className).toContain("status-hud-blink"));
});

test("shows yellow when LLM reports warn", async () => {
  const fetchMock = vi.fn(() =>
    okResponse({ ok: true, checks: { db: "ok", llm: "warn" } })
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<ChatStatusHud busy={false} />);

  const llmLamp = await screen.findByTestId("lamp-llm-dot");
  expect(llmLamp.className).toContain("bg-amber-400");
});

test("non-json ready response marks DB and LLM as err", async () => {
  const fetchMock = vi.fn(() => htmlResponse("<html></html>"));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChatStatusHud busy={false} />);

  const dbLamp = await screen.findByTestId("lamp-db");
  const llmLamp = await screen.findByTestId("lamp-llm-dot");
  expect(dbLamp.className).toContain("bg-rose-500");
  expect(llmLamp.className).toContain("bg-rose-500");
});

test("does not blink when LLM is err even if busy", async () => {
  const fetchMock = vi.fn(() =>
    okResponse({ ok: true, checks: { db: "ok", llm: "err" } })
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<ChatStatusHud busy />);

  const llmLamp = await screen.findByTestId("lamp-llm-dot");
  expect(llmLamp.className).not.toContain("status-hud-blink");
});
