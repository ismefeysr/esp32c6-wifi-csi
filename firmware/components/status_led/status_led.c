/*
 * SPDX-License-Identifier: MIT
 */
#include "status_led.h"
#include "esp_check.h"
#include "led_strip.h"

static const char *TAG = "status_led";

esp_err_t status_led_init(uint8_t red, uint8_t green, uint8_t blue)
{
    led_strip_handle_t led;
    led_strip_config_t strip_config = {
        .strip_gpio_num = STATUS_LED_GPIO,
        .max_leds = 1,
    };
    led_strip_rmt_config_t rmt_config = {
        .resolution_hz = 10 * 1000 * 1000,
    };
    ESP_RETURN_ON_ERROR(led_strip_new_rmt_device(&strip_config, &rmt_config, &led), TAG, "create LED device");
    ESP_RETURN_ON_ERROR(led_strip_set_pixel(led, 0, red, green, blue), TAG, "set pixel");
    return led_strip_refresh(led);
}
