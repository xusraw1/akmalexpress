const sidebar = document.getElementById("sidebar-multi-level-sidebar");

let sidebarToggle = false;

// Sidebar toggle handler
const sidebarToggleHandler = () => {
  if (window.innerWidth > 1023 && sidebar.classList.contains("-translate-x-full")) sidebar.classList.remove("-translate-x-full");
  else sidebar.classList.add("-translate-x-full");
};
sidebarToggleHandler();

window.addEventListener("resize", sidebarToggleHandler);
