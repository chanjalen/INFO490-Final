document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-search-panel]").forEach((panel) => {
        const focusInput = panel.querySelector("[data-focus-input]");
        const searchInput = panel.querySelector("[data-search-input]");
        const chips = panel.querySelectorAll("[data-focus-chip]");
        const helperCopies = panel.querySelectorAll("[data-focus-copy]");
        const defaultPlaceholder = "What do you remember?";

        const syncState = () => {
            const activeFocus = focusInput?.value || "";
            chips.forEach((chip) => {
                chip.classList.toggle("is-active", chip.dataset.focusName === activeFocus);
            });
            helperCopies.forEach((copy) => {
                const key = copy.dataset.focusCopy || "default";
                copy.classList.toggle(
                    "is-active",
                    activeFocus ? key === activeFocus : key === "default",
                );
            });
        };

        chips.forEach((chip) => {
            chip.addEventListener("click", () => {
                const nextFocus = chip.dataset.focusName || "";
                const placeholder = chip.dataset.focusPlaceholder || defaultPlaceholder;
                const isAlreadyActive = focusInput.value === nextFocus;

                focusInput.value = isAlreadyActive ? "" : nextFocus;
                searchInput.placeholder = isAlreadyActive ? defaultPlaceholder : placeholder;
                searchInput.focus();
                syncState();
            });
        });

        syncState();
    });
});
