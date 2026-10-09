/** "smooth" unless the user asked for less motion (JS scrolling ignores the CSS rule). */
export function smoothScroll(): ScrollBehavior {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}
