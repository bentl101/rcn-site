(function () {
  "use strict";

  var root = document.documentElement;
  var storageKey = "rcn-review-preview-theme";
  var savedTheme = null;

  try {
    savedTheme = window.localStorage.getItem(storageKey);
  } catch (error) {
    savedTheme = null;
  }

  if (savedTheme === "dark") root.classList.add("dark");
  if (savedTheme === "light") root.classList.add("light");

  function isDark() {
    if (root.classList.contains("dark")) return true;
    if (root.classList.contains("light")) return false;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function syncThemeButtons() {
    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      var dark = isDark();
      button.setAttribute("aria-pressed", String(dark));
      button.setAttribute("aria-label", dark ? "Use light theme" : "Use dark theme");
      var use = button.querySelector("use");
      if (use) use.setAttribute("href", dark ? "#icon-sun" : "#icon-moon");
    });
  }

  document.addEventListener("click", function (event) {
    var themeButton = event.target.closest("[data-theme-toggle]");
    if (themeButton) {
      var nextTheme = isDark() ? "light" : "dark";
      root.classList.toggle("dark", nextTheme === "dark");
      root.classList.toggle("light", nextTheme === "light");
      try { window.localStorage.setItem(storageKey, nextTheme); } catch (error) { /* Preview still works without storage. */ }
      syncThemeButtons();
      return;
    }

    var navButton = event.target.closest("[data-nav-toggle]");
    if (navButton) {
      var targetId = navButton.getAttribute("aria-controls");
      var target = document.getElementById(targetId);
      var expanded = navButton.getAttribute("aria-expanded") === "true";
      navButton.setAttribute("aria-expanded", String(!expanded));
      if (target) target.toggleAttribute("data-open", !expanded);
      return;
    }

    var nextButton = event.target.closest("[data-form-next]");
    if (nextButton) {
      updateFormStep(nextButton.closest("[data-preview-form]"), 2);
      return;
    }

    var backButton = event.target.closest("[data-form-back]");
    if (backButton) updateFormStep(backButton.closest("[data-preview-form]"), 1);
  });

  document.querySelectorAll("[data-concept-select]").forEach(function (select) {
    select.addEventListener("change", function () {
      if (select.value) window.location.href = select.value;
    });
  });

  function updateFormStep(form, step) {
    if (!form) return;
    form.querySelectorAll("[data-form-step]").forEach(function (panel) {
      panel.hidden = Number(panel.dataset.formStep) !== step;
    });
    var progress = form.querySelector("[data-form-progress]");
    if (progress) {
      progress.setAttribute("aria-valuenow", String(step * 50));
      progress.style.setProperty("--progress-value", String(step * 50) + "%");
    }
    var label = form.querySelector("[data-form-progress-label]");
    if (label) label.textContent = "Step " + step + " of 2";
  }

  document.querySelectorAll("form[data-preview-form]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var status = form.querySelector("[data-preview-status]");
      if (status) status.textContent = "Preview only — no details were sent or stored.";
      showToast("Preview only: this form does not submit or track data.");
    });
  });

  var toastTimer;
  function showToast(message) {
    var toast = document.querySelector("[data-toast]");
    if (!toast) return;
    toast.textContent = message;
    toast.dataset.visible = "true";
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () { toast.dataset.visible = "false"; }, 4200);
  }

  function setupCarousel(carousel) {
    var track = carousel.querySelector(".review-track");
    var cards = Array.from(carousel.querySelectorAll(".review-card"));
    var previous = carousel.querySelector("[data-carousel-prev]");
    var next = carousel.querySelector("[data-carousel-next]");
    var status = carousel.querySelector("[data-carousel-status]");
    var dots = carousel.querySelector(".carousel-dots");
    var activeIndex = 0;
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

    function goTo(index) {
      var bounded = Math.max(0, Math.min(cards.length - 1, index));
      var left = cards[bounded].offsetLeft - track.offsetLeft;
      track.scrollTo({ left: left, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      activeIndex = bounded;
      update();
    }

    function nearestIndex() {
      var target = track.scrollLeft;
      var closest = 0;
      var distance = Infinity;
      cards.forEach(function (card, index) {
        var current = Math.abs(card.offsetLeft - track.offsetLeft - target);
        if (current < distance) { distance = current; closest = index; }
      });
      return closest;
    }

    function update() {
      activeIndex = nearestIndex();
      if (status) status.textContent = "Review " + (activeIndex + 1) + " of " + cards.length;
      if (previous) previous.disabled = activeIndex === 0;
      if (next) next.disabled = activeIndex === cards.length - 1;
      if (dots) {
        dots.querySelectorAll(".carousel-dot").forEach(function (dot, index) {
          dot.setAttribute("aria-current", String(index === activeIndex));
        });
      }
    }

    if (previous) previous.addEventListener("click", function () { goTo(activeIndex - 1); });
    if (next) next.addEventListener("click", function () { goTo(activeIndex + 1); });
    if (dots) dots.addEventListener("click", function (event) {
      var dot = event.target.closest("[data-carousel-index]");
      if (dot) goTo(Number(dot.dataset.carouselIndex));
    });
    track.addEventListener("keydown", function (event) {
      if (event.key === "ArrowRight") { event.preventDefault(); goTo(activeIndex + 1); }
      if (event.key === "ArrowLeft") { event.preventDefault(); goTo(activeIndex - 1); }
    });
    var scrollFrame;
    track.addEventListener("scroll", function () {
      window.cancelAnimationFrame(scrollFrame);
      scrollFrame = window.requestAnimationFrame(update);
    }, { passive: true });
    window.addEventListener("resize", update, { passive: true });
    update();
  }

  document.querySelectorAll(".review-carousel").forEach(setupCarousel);

  var filterStatus = document.querySelector("[data-filter-status]");
  document.querySelectorAll("[data-review-filter]").forEach(function (button) {
    button.addEventListener("click", function () {
      var filter = button.dataset.reviewFilter;
      document.querySelectorAll("[data-review-filter]").forEach(function (item) {
        item.setAttribute("aria-pressed", String(item === button));
      });
      var visible = 0;
      document.querySelectorAll("[data-review-tags]").forEach(function (card) {
        var tags = card.dataset.reviewTags.split(" ");
        var show = filter === "all" || tags.includes(filter);
        card.hidden = !show;
        if (show) visible += 1;
      });
      if (filterStatus) filterStatus.textContent = visible + " reviews shown";
    });
  });

  var reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    reveals.forEach(function (item) { observer.observe(item); });
  } else {
    reveals.forEach(function (item) { item.classList.add("is-visible"); });
  }

  syncThemeButtons();
})();
