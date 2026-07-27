const approval = document.querySelector("#approve-writeback");
const button = document.querySelector("#publish-button");
const form = document.querySelector("#publish-form");
const status = document.querySelector("#form-status");

if (approval && button) {
  approval.addEventListener("change", () => {
    button.textContent = approval.checked ? "Publish approved evidence" : "Preview write-back";
  });
}

if (form && button && status) {
  form.addEventListener("submit", () => {
    button.disabled = true;
    status.textContent = approval && approval.checked
      ? "Publishing and rereading DataHub evidence…"
      : "Building a mutation-free preview…";
  });
}
