import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "../src/i18n/i18n";
import LanguageSwitcher from "../src/components/LanguageSwitcher";
import Modal from "../src/components/Modal";

type VTDocument = Document & { startViewTransition?: unknown };

beforeEach(async () => {
  await i18n.changeLanguage("en");
});
afterEach(() => {
  delete (document as VTDocument).startViewTransition;
  delete document.documentElement.dataset.fade;
  delete document.documentElement.dataset.transition;
});

describe("nothing changes instantly", () => {
  it("switches language through a view transition when the browser has one", async () => {
    const start = vi.fn((update: () => Promise<void>) => ({
      finished: update(),
    }));
    (document as VTDocument).startViewTransition = start;
    const user = userEvent.setup();
    render(<LanguageSwitcher />);
    await user.click(screen.getByRole("button", { name: "Română" }));
    expect(start).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(i18n.resolvedLanguage).toBe("ro"));
  });

  it("fades the page in after a language switch without view transitions", async () => {
    const user = userEvent.setup();
    render(<LanguageSwitcher />);
    await user.click(screen.getByRole("button", { name: "Русский" }));
    await waitFor(() =>
      expect(document.documentElement.dataset.fade).toBe("language"),
    );
    expect(i18n.resolvedLanguage).toBe("ru");
  });

  it("keeps a dialog on screen, marked as closing, while it fades out", async () => {
    const { rerender } = render(
      <Modal title="Edit" open onClose={() => {}}>
        <p>Body</p>
      </Modal>,
    );
    expect(screen.getByText("Body")).toBeTruthy();
    rerender(
      <Modal title="Edit" open={false} onClose={() => {}}>
        <p>Body</p>
      </Modal>,
    );
    expect(document.querySelector("dialog")?.getAttribute("data-closing")).toBe(
      "true",
    );
    await waitFor(() => expect(screen.queryByText("Body")).toBeNull());
  });
});
