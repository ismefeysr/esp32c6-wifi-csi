/*
 * SPDX-License-Identifier: MIT
 *
 * Onboard RGB status LED used to tell the sender and receiver boards apart.
 */
#pragma once

#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Onboard WS2812 on the ESP32-C6-DevKit */
#define STATUS_LED_GPIO          8

/* Board identification colours (kept dim on purpose) */
#define STATUS_LED_COLOR_SENDER   0, 20, 0      /* green */
#define STATUS_LED_COLOR_RECEIVER 0, 0, 20      /* blue  */

/**
 * @brief Initialise the onboard RGB LED and light it in the given colour.
 *
 * Called once at boot; the LED is not touched afterwards, so it has no effect
 * on the Wi-Fi / ESP-NOW timing.
 */
esp_err_t status_led_init(uint8_t red, uint8_t green, uint8_t blue);

#ifdef __cplusplus
}
#endif
