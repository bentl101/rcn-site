(function () {
  "use strict";

  function setupCarousel(carousel) {
    var track = carousel.querySelector(".review-track");
    var cards = Array.from(carousel.querySelectorAll(".review-card"));
    var previous = carousel.querySelector("[data-carousel-prev]");
    var next = carousel.querySelector("[data-carousel-next]");
    var status = carousel.querySelector("[data-carousel-status]");
    var dots = carousel.querySelector(".carousel-dots");
    var activeIndex = 0;
    var scrollFrame = null;
    var resizeFrame = null;

    if (!track || cards.length === 0) return;

    if (dots) {
      cards.forEach(function (_, index) {
        var dot = document.createElement("button");
        dot.type = "button";
        dot.className = "carousel-dot";
        dot.setAttribute("aria-label", "Show review " + (index + 1));
        dot.dataset.carouselIndex = String(index);
        dots.appendChild(dot);
      });
    }

    function canScroll() {
      return track.scrollWidth > track.clientWidth + 2;
    }

    function nearestIndex() {
      var target = track.scrollLeft;
      var closest = 0;
      var distance = Infinity;

      cards.forEach(function (card, index) {
        var current = Math.abs(card.offsetLeft - track.offsetLeft - target);
        if (current < distance) {
          distance = current;
          closest = index;
        }
      });

      return closest;
    }

    function update() {
      var scrollable = canScroll();
      carousel.classList.toggle("is-scrollable", scrollable);
      activeIndex = scrollable ? nearestIndex() : 0;

      if (status) status.textContent = "Review " + (activeIndex + 1) + " of " + cards.length;
      if (previous) previous.disabled = !scrollable || activeIndex === 0;
      if (next) next.disabled = !scrollable || activeIndex === cards.length - 1;

      if (dots) {
        dots.querySelectorAll(".carousel-dot").forEach(function (dot, index) {
          if (index === activeIndex) {
            dot.setAttribute("aria-current", "true");
          } else {
            dot.removeAttribute("aria-current");
          }
        });
      }
    }

    function goTo(index) {
      if (!canScroll()) return;

      var bounded = Math.max(0, Math.min(cards.length - 1, index));
      var left = cards[bounded].offsetLeft - track.offsetLeft;
      var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      track.scrollTo({
        left: left,
        behavior: reducedMotion ? "auto" : "smooth"
      });
      activeIndex = bounded;
      update();
    }

    if (previous) {
      previous.addEventListener("click", function () {
        goTo(activeIndex - 1);
      });
    }

    if (next) {
      next.addEventListener("click", function () {
        goTo(activeIndex + 1);
      });
    }

    if (dots) {
      dots.addEventListener("click", function (event) {
        var dot = event.target.closest("[data-carousel-index]");
        if (dot) goTo(Number(dot.dataset.carouselIndex));
      });
    }

    track.addEventListener("keydown", function (event) {
      if (event.key === "ArrowRight") {
        event.preventDefault();
        goTo(activeIndex + 1);
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        goTo(activeIndex - 1);
      }
    });

    track.addEventListener("scroll", function () {
      window.cancelAnimationFrame(scrollFrame);
      scrollFrame = window.requestAnimationFrame(update);
    }, { passive: true });

    window.addEventListener("resize", function () {
      window.cancelAnimationFrame(resizeFrame);
      resizeFrame = window.requestAnimationFrame(update);
    }, { passive: true });

    if ("ResizeObserver" in window) {
      new ResizeObserver(update).observe(track);
    }

    update();
  }

  document.querySelectorAll("[data-review-carousel]").forEach(setupCarousel);
})();
