#include <algorithm>
#include <vector>
#include <math.h>
#include <SPI.h>
#include <TFT_eSPI.h>

// Custom Fonts: https://www.youtube.com/watch?v=4zYaIJxEYaM
#include "AirbusDisplayNumbersFont.h"

// https://github.com/mboehmerm/Three-IPS-Displays-with-ST7789-170x320-240x280-240x320/tree/main/ESP32_C3
// Setup for ESP32 C3 super mini
/*
Install Board Manager: esp32 by Espressif Systems v3.2.1

Edit the file TFT_eSPI_ESP32_C3.h, located at:
C:\Users<username>\Documents\Arduino\libraries\TFT_eSPI\Processors\TFT_eSPI_ESP32_C3.h

Replace line 71:
#define SPI_PORT SPI2_HOST

with:
#if ESP_ARDUINO_VERSION_MAJOR < 3
  #define SPI_PORT SPI2_HOST
#else
  #define SPI_PORT 2
#endif

Replace:
#ifndef REG_SPI_BASE
  #define REG_SPI_BASE(i) DR_REG_SPI2_BASE
#endif

with:
#ifdef REG_SPI_BASE
  #undef REG_SPI_BASE
#endif

#define REG_SPI_BASE(i) (((i)==2) ? (DR_REG_SPI2_BASE) : (DR_REG_SPI0_BASE - ((i) * 0x1000)))
*/

//   #########################################################################
//   ###### DON'T FORGET TO UPDATE THE User_Setup.h FILE IN THE LIBRARY ######
//   #########################################################################

#define BUZZER_PIN 10

#define BL_PIN 1

#define RXD1 20
#define TXD1 21

TFT_eSPI tft = TFT_eSPI();
#define TFT_GREY 0x5AEB
#define TFT_AMBER 0xEC00
#define TFT_DARKBROWN 0x5941
#define LIGHT_RED 0xFBAE
#define GREY_RED 0x9986
#define DARK_RED 0x8000

uint32_t updateTime = millis();

boolean test_mode = false;

uint32_t lastDataTime = millis();
boolean gps_module_connected = false;
boolean gps_signal = false;

boolean car_connected = false;

bool buzzerActive = false;
const int MAX_BUZZER_STEPS = 8;
int buzzerStepCount = 0;
int buzzerCurrentStep = 0;
unsigned long buzzerStepStart = 0;

String current_date = "";
String current_time = "";
String displayed_time = current_time;

String vary = "";
String category = "";
String zoneReason = "";
String zoneName = "";
String zoneArea = "";

String location_str = "";
String displayed_location_str = location_str;

String speedCamDescription = "";
String speedCamStreet = "";
String speedCamSuburb = "";
String speedCamLocation = "";

String speedCam_str = "";
String displayed_speedCam_str = speedCam_str;
bool speedcamAlertMode = false;
unsigned long lastSpeedcamToggleTime = 0;
bool speedcamColourToggleState = false;

float speedCamDistance = -1;
float displayed_speedCamDistance = -1;

boolean rerender_speedcam_popup = false;

String speed_source = "NIL"; // W: weighted, G: gps raw, C: car obd
String displayed_speed_source = speed_source;

float indicated_speed = -1;
float new_displayed_speed = indicated_speed;
float displayed_speed = indicated_speed;

int speed_prediction = -999;
float new_displayed_speed_prediction = speed_prediction;
float displayed_speed_prediction = speed_prediction;

int max_speed = 100;
float new_displayed_max_speed = max_speed;
float displayed_max_speed = max_speed;
int overspeed_red_speed = 20;  // <20 over is yellow, >20 over is red
bool prev_overspeeding = false;

boolean wifi = "";
boolean displayed_wifi = wifi;

uint8_t num_sats = 0;
uint8_t displayed_num_sats = num_sats;

float indicated_rpm = -1;
float new_displayed_rpm = round(indicated_rpm * 10.0) / 10.0;
float displayed_rpm = round(indicated_rpm * 10.0) / 10.0;
float red_line_rpm = 4000.0;
float max_rpm = 4800.0;

float fuel_flow = -1;
float displayed_ff = round(fuel_flow * 10.0) / 10.0;

float fuel_efficiency = -1;
float displayed_fe = round(fuel_efficiency * 10.0) / 10.0;

float ev_charge = -1;
int displayed_evchrg = int(round(ev_charge));

std::vector<std::pair<String, uint16_t>> memos;
std::vector<std::pair<String, uint16_t>> displayed_memos;


int line_w = 2;

int speed_bar_w = 90;
int speed_bar_h = 320;
int speed_bar_border_extends = 15;
int speed_strip_line_l = 15; // Length of line in speed strip
int speed_strip_dist = 50;  // Distance between lines (10 speed units)

int status_disp_x = speed_bar_w;
int status_disp_y = 0;
int status_disp_h = 50;
int status_disp_w = 480 - status_disp_x;

int engine_inst_lgap = 20;
int engine_inst_w = 160;
int engine_inst_h = 320;

int warning_disp_x = speed_bar_w + engine_inst_lgap - 10;
int warning_disp_y = 200;
int warning_disp_w = (480 - speed_bar_w - engine_inst_lgap) * 0.5;
int warning_disp_h = 120;

int memo_disp_x = speed_bar_w + engine_inst_lgap + warning_disp_w + 15;
int memo_disp_y = warning_disp_y;
int memo_disp_w = (480 - speed_bar_w - engine_inst_lgap) * 0.5;
int memo_disp_h = 120;

int speedcam_disp_x = warning_disp_x + 25;
int speedcam_disp_y = status_disp_h + 5;
int speedcam_disp_w = 480 - warning_disp_x - 50;
int speedcam_disp_h = warning_disp_y - status_disp_h - 20;


std::vector<String> wrapTextLines(TFT_eSprite& sprite, const String& text, int maxWidth) {
    std::vector<String> lines;
    String word, line;

    for (int i = 0; i <= text.length(); ++i) {
        char c = text[i];
        if (c == ' ' || c == '\n' || c == '\0') {
            // Check if current word fits in line
            String testLine = line + (line.length() > 0 ? " " : "") + word;
            if (sprite.textWidth(testLine) > maxWidth && line.length() > 0) {
                lines.push_back(line);
                line = word;
            } else {
                if (line.length() > 0) line += " ";
                line += word;
            }

            if (c == '\n') {
                lines.push_back(line);
                line = "";
            }

            word = "";
        } else {
            word += c;
        }
    }

    // Add remaining word (if any) to the line
    if (word.length() > 0) {
        String testLine = line + (line.length() > 0 ? " " : "") + word;
        if (sprite.textWidth(testLine) > maxWidth && line.length() > 0) {
            lines.push_back(line);
            line = word;
        } else {
            if (line.length() > 0) line += " ";
            line += word;
        }
    }

    if (line.length() > 0) {
        lines.push_back(line);
    }

    return lines;
}


class SpeedBar {
    private:
    int spd_ind_h = 40;
    int spd_ind_w = speed_bar_w - 35;
    int spd_ind_y = speed_bar_h / 2 - spd_ind_h / 2;
    int spd_ind_mid_y = spd_ind_y + spd_ind_h / 2;

    void makeSpeedBarHorizontalBorder(uint16_t color) {
        speed_bar.fillRect(line_w, 0, speed_bar_w, line_w, color);  // Top white line
        speed_bar.fillRect(line_w, speed_bar_h - line_w, speed_bar_w, line_w, color);  // Bottom white line
    }
    
    void makeSpeedBarVerticalBorder(uint16_t color) {
        speed_bar.fillRect(speed_bar_w - speed_bar_border_extends, 0, line_w, speed_bar_h, color);  // Right vertial white line
    }

    void makeSpeedTrend(float spd_trend_y, uint16_t color) {
        if (spd_trend_y != spd_ind_mid_y) {
            speed_bar.fillRect(spd_ind_w + 10 - 2, min((int)spd_trend_y, spd_ind_mid_y), 2, abs(spd_trend_y - spd_ind_mid_y), color);
            // speed_bar.fillTriangle(spd_ind_w + 10 - 2, spd_trend_y, spd_ind_w + 10 + 1, spd_trend_y - 5, spd_ind_w + 10 - 6, spd_trend_y - 5, color);
            if (spd_trend_y > spd_ind_mid_y) {
                speed_bar.drawWideLine(spd_ind_w + 10 - 2, spd_trend_y, spd_ind_w + 10 - 5, spd_trend_y - 5, 1, color, color);
                speed_bar.drawWideLine(spd_ind_w + 10 - 1, spd_trend_y, spd_ind_w + 10 + 2, spd_trend_y - 5, 1, color, color);
            } else {
                speed_bar.drawWideLine(spd_ind_w + 10 - 2, spd_trend_y, spd_ind_w + 10 - 5, spd_trend_y + 5, 1, color, color);
                speed_bar.drawWideLine(spd_ind_w + 10 - 1, spd_trend_y, spd_ind_w + 10 + 2, spd_trend_y + 5, 1, color, color);
            }
        }
    }
    
    void updateSpeedStrip() {
        speed_bar.loadFont(PFDFont25);
        speed_bar.setTextColor(TFT_WHITE, TFT_GREY);
        speed_bar.setTextDatum(MR_DATUM);
        int text_height = speed_bar.fontHeight();
    
        int line_x_left = speed_bar_w - speed_bar_border_extends - speed_strip_line_l;

        float zero_spd_y_old = (speed_bar_h / 2) + ((displayed_speed / 10.0) * speed_strip_dist);
        float zero_spd_y = (speed_bar_h / 2) + ((new_displayed_speed / 10.0) * speed_strip_dist);
        
        float target_spd_y_old = zero_spd_y_old;
        float target_spd_y = zero_spd_y;
        
        float spd_trend_y_old = zero_spd_y_old - ((displayed_speed_prediction / 10.0) * speed_strip_dist);
        float spd_trend_y = zero_spd_y - ((new_displayed_speed_prediction / 10.0) * speed_strip_dist);

        // Cover old speed trend
        if (displayed_speed_prediction != -1 && displayed_speed_prediction != displayed_speed) {
            makeSpeedTrend(spd_trend_y_old, TFT_GREY);
        }

        for (int spd10 = 0; target_spd_y_old >= -5 || target_spd_y >= -5; spd10 += 1) {  // Put -5 as minimum instead of 0 for buffer
            if ((target_spd_y_old >= -5 && target_spd_y_old <= speed_bar_h + 5) || (target_spd_y >= -5 && target_spd_y <= speed_bar_h + 5)) {  // Put -5 min and 5 max instead of 0 for buffer
                
                // Speed lines
                speed_bar.fillRect(line_x_left, target_spd_y_old, speed_strip_line_l, line_w, TFT_GREY);  // Cover old line
                speed_bar.fillRect(line_x_left, target_spd_y, speed_strip_line_l, line_w, TFT_WHITE);  // Add new line
    
                // Speed numbers
                if (spd10 % 2 == 0) {
                    int text_width = speed_bar.textWidth(String(spd10 * 10));
                    speed_bar.fillRect(line_x_left - 5 - text_width, target_spd_y_old - text_height/2, text_width, text_height, TFT_GREY);  // Cover old text
                    speed_bar.drawString(String(spd10 * 10), line_x_left - 5, target_spd_y);  // Add new text
                }

            }
            
            target_spd_y_old -= speed_strip_dist;
            target_spd_y -= speed_strip_dist;
        }

        // Add new speed trend
        float prediction_delta = new_displayed_speed_prediction - new_displayed_speed;  // Positive if arrow pointing up, Negative if arrow pointing down
        if (speed_prediction != -999 && abs(prediction_delta) >= 1 && 
        !(new_displayed_speed <= 3 && prediction_delta <= 0)) {  // Speed trend is not shown if speed is less than 3 and is a negative delta
            makeSpeedTrend(spd_trend_y, TFT_YELLOW);
        }
    }
    
    void updateOverspeedStrip() {
        speed_bar.fillRect(speed_bar_w - speed_bar_border_extends, line_w, speed_bar_border_extends, speed_bar_h - 2*line_w, TFT_BLACK);
        makeSpeedBarVerticalBorder(TFT_WHITE);
        
        float zero_spd_y = (speed_bar_h / 2) + ((new_displayed_speed / 10.0) * speed_strip_dist);
        float overspeed_y = zero_spd_y - speed_strip_dist * (new_displayed_max_speed / 10);
        
        if (overspeed_y < 0) {return;}
    
        int block_w = 10;
        int block_h = 9;
        int block_gap = 8;
        int block_x = speed_bar_w - speed_bar_border_extends + line_w - 1;
        speed_bar.drawFastVLine(block_x + block_w, line_w, overspeed_y - line_w - 1, TFT_DARKBROWN);  // Custom colour: https://barth-dev.de/online/rgb565-color-picker/
        for (int target_overspeed_y = overspeed_y; target_overspeed_y >= -5; target_overspeed_y -= (block_h + block_gap)) {
            if (target_overspeed_y >= -5 && target_overspeed_y <= speed_bar_h + 5) {  // Put -5 min and 5 max instead of 0 for buffer
                int colour = target_overspeed_y > overspeed_y - speed_strip_dist * (overspeed_red_speed / 10.0) ? TFT_AMBER : TFT_RED;
                speed_bar.fillRect(block_x, target_overspeed_y - block_h, block_w, block_h * 0.8, colour);
            }
        }
    }
    
    void updateSpeedIndicator() {
        speed_bar.fillRect(0, spd_ind_y, spd_ind_w, spd_ind_h, TFT_WHITE);
        speed_bar.fillTriangle(spd_ind_w, spd_ind_mid_y - 6, spd_ind_w + 10, spd_ind_mid_y, spd_ind_w, spd_ind_mid_y + 6, TFT_WHITE);
        speed_bar.fillRect(line_w, spd_ind_y + line_w, spd_ind_w - 2*line_w, spd_ind_h - 2*line_w, TFT_BLACK);
        speed_bar.fillTriangle(spd_ind_w - line_w, spd_ind_mid_y - 4, spd_ind_w + 6, spd_ind_mid_y, spd_ind_w - line_w, spd_ind_mid_y + 4, TFT_BLACK);
        speed_bar.fillRect(spd_ind_w + 10, spd_ind_mid_y, 25, line_w, TFT_YELLOW);
        speed_bar.fillTriangle(speed_bar_w - speed_bar_border_extends, spd_ind_mid_y, speed_bar_w, spd_ind_mid_y + 5, speed_bar_w, spd_ind_mid_y - 5, TFT_YELLOW);
    
        speed_bar.loadFont(PFDFont35);
        speed_bar.setTextColor(TFT_WHITE, TFT_BLACK);
        speed_bar.setTextDatum(MC_DATUM);
        char speedStr[4];
        sprintf(speedStr, "%03d", (int)round(new_displayed_speed));
        speed_bar.drawString(String(speedStr), (speed_bar_w - 35) / 2, speed_bar_h / 2, 2);
    }

    public:
    TFT_eSprite speed_bar = TFT_eSprite(&tft);

    void setup() {
        speed_bar.setColorDepth(8);
        speed_bar.createSprite(speed_bar_w, speed_bar_h);
        speed_bar.fillSprite(TFT_BLACK);

        speed_bar.fillRect(line_w, line_w, speed_bar_w - speed_bar_border_extends - line_w, speed_bar_h - 2*line_w, TFT_GREY);
        update(true);
    }

    void update(boolean force=false) {
        const float smoothing = 0.1f;
        if (force || displayed_speed != indicated_speed || displayed_max_speed != max_speed  || displayed_speed_prediction != speed_prediction) {
            if (indicated_speed == -1) {
                new_displayed_speed = indicated_speed;
                new_displayed_max_speed = max_speed;
                speed_bar.fillSprite(TFT_BLACK);
                makeSpeedBarVerticalBorder(TFT_RED);
                makeSpeedBarHorizontalBorder(TFT_RED);
                speed_bar.fillRect(line_w, line_w, speed_bar_w - speed_bar_border_extends - line_w, speed_bar_h - 2*line_w, TFT_GREY);
            } else {
                if (abs(displayed_speed - indicated_speed) > 0.3f && displayed_speed >= 0) {  // Smooth animation when difference is greater than x, also ensuring the speed does not start from negative when no speed
                    new_displayed_speed = displayed_speed + (indicated_speed - displayed_speed) * smoothing;
                } else {
                    new_displayed_speed = indicated_speed;
                }

                if (abs(displayed_max_speed - max_speed) > 0.3f) {
                    new_displayed_max_speed = displayed_max_speed + (max_speed - displayed_max_speed) * smoothing;
                } else {
                    new_displayed_max_speed = max_speed;
                }

                if (abs(displayed_speed_prediction - speed_prediction) > 0.3f && displayed_speed_prediction != -999) {
                    new_displayed_speed_prediction = displayed_speed_prediction + (speed_prediction - displayed_speed_prediction) * smoothing;
                } else if (speed_prediction != -999 && displayed_speed_prediction == -999) {  // Speed prediction was enabled
                    new_displayed_speed_prediction = new_displayed_speed;  // Make predicted speed arise from center (current displayed speed)
                } else {
                    new_displayed_speed_prediction = speed_prediction;
                }
                
                updateSpeedStrip();
                makeSpeedBarVerticalBorder(TFT_WHITE);
                updateOverspeedStrip();
                makeSpeedBarHorizontalBorder(TFT_WHITE);
                updateSpeedIndicator();
            }
            
            speed_bar.pushSprite(0, 0, TFT_TRANSPARENT);
            displayed_speed = new_displayed_speed;
            displayed_max_speed = new_displayed_max_speed;
            displayed_speed_prediction = new_displayed_speed_prediction;
        }
    }
};


class StatusDisplay {
    public:
    TFT_eSprite status_disp = TFT_eSprite(&tft);

    int col1_width = 90 - line_w / 2;
    int col2_width = 180 - line_w / 2;
    int col3_width = 270 - line_w / 2;
    
    void setup() {
        status_disp.setColorDepth(8);
        status_disp.createSprite(status_disp_w, status_disp_h);
        status_disp.fillSprite(TFT_RED);

        update(true);
    }

    void update(boolean force=false) {
        if (force || displayed_speed_source != speed_source || displayed_wifi != wifi || displayed_num_sats != num_sats || displayed_time != current_time) {
            status_disp.fillSprite(TFT_BLACK);

            status_disp.fillRect(col1_width, 0, line_w, status_disp_h - 10, TFT_WHITE);
            status_disp.fillRect(col2_width, 0, line_w, status_disp_h - 10, TFT_WHITE);
            status_disp.fillRect(col3_width, 0, line_w, status_disp_h - 10, TFT_WHITE);

            status_disp.loadFont(ECAMFont20);
            status_disp.setTextDatum(TC_DATUM);

            status_disp.setTextColor(TFT_WHITE, TFT_BLACK);
            status_disp.drawString(speed_source + "/S", col1_width / 2, 5);

            status_disp.setTextColor(TFT_GREEN, TFT_BLACK);
            status_disp.drawString("", col1_width + (line_w / 2) + (col1_width / 2), 5);

            if (gps_module_connected) {
                status_disp.setTextColor(TFT_WHITE, TFT_BLACK);
                status_disp.drawString(String(num_sats) + " SATS", col2_width + (line_w / 2) + (col1_width / 2), 5);
            }

            if (car_connected) {
                status_disp.setTextColor(TFT_GREEN, TFT_BLACK);
                status_disp.drawString("CAR CON", col2_width + (line_w / 2) + (col1_width / 2), 25);
            }

            status_disp.setTextDatum(TR_DATUM);
            status_disp.setTextColor(TFT_GREEN, TFT_BLACK);
            status_disp.drawString(current_time, 480 - status_disp_x - 5, 5);
            status_disp.drawString(current_date, 480 - status_disp_x - 5, 25);
    
            status_disp.pushSprite(status_disp_x, status_disp_y);

            displayed_speed_source = speed_source;
            displayed_wifi = wifi;
            displayed_num_sats = num_sats;
            displayed_time = current_time;
            rerender_speedcam_popup = true;
        }
    }
};


class EngineInstruments {
    private:
    int gauge_radius = 60;  // Arc height is 90
    int gauge_height = 100;

    void drawGaugeTickmark(TFT_eSprite *sprite, int h, int k, int r, int pretrusion, int intrusion, int angle, uint16_t color) {
        angle = angle + 90;  // Adjust since arc angles start at 6 o'clock
        int x_outer = h + (r + pretrusion) * cos(angle * PI / 180);
        int y_outer = k + (r + pretrusion) * sin(angle * PI / 180);
        int x_inner = h + (r - intrusion) * cos(angle * PI / 180);
        int y_inner = k + (r - intrusion) * sin(angle * PI / 180);
    
        sprite->drawLine(x_outer, y_outer, x_inner, y_inner, color);
    }

    void drawGauge(TFT_eSprite *sprite, int x, int y, int r, int start_angle, int end_angle, float red_value, float max_value, float current_value, float prev_value, float tick_freq_value, uint16_t base_color, const char* label, const char* units) {
        sprite->fillSprite(TFT_BLACK);
        
        // drawGaugeTickmark(sprite, x + r, y + r, r, 5, r, (start_angle + (prev_value / max_value) * (end_angle - start_angle)), TFT_BLACK);
        
        int red_start_angle = start_angle + (red_value / max_value) * (end_angle - start_angle);
        if (start_angle != red_start_angle) {
            sprite->drawArc(x + r, y + r, r + line_w - 1, r, start_angle, red_start_angle, base_color, TFT_BLACK);
        }
        if (end_angle != red_start_angle) {
            sprite->drawArc(x + r, y + r, r + line_w - 1, r, red_start_angle, end_angle - 1, TFT_RED, TFT_BLACK);
        }
        
        if (tick_freq_value > 0) {
            sprite->drawArc(x + r, y + r, r + line_w - 6, r - 5, red_start_angle, end_angle - 1, TFT_RED, TFT_BLACK);
            
            for (float i = 0; i <= max_value; i += tick_freq_value) {
                int angle = start_angle + (i / max_value) * (end_angle - start_angle);
                int colour = i <= red_value ? base_color : TFT_RED;
                drawGaugeTickmark(sprite, x + r, y + r, r, 0, 5, angle, colour);
            }
            drawGaugeTickmark(sprite, x + r, y + r, r, 0, 5, red_start_angle, base_color);
            drawGaugeTickmark(sprite, x + r, y + r, r, 0, 5, end_angle, TFT_RED);

            drawGaugeTickmark(sprite, x + r, y + r, r, 5, r, (start_angle + (current_value / max_value) * (end_angle - start_angle)), TFT_GREEN);
        }
        
        sprite->loadFont(ECAMFont20);
        sprite->setTextDatum(TC_DATUM);
        sprite->setTextColor(TFT_WHITE, TFT_TRANSPARENT);
        sprite->drawString(label, x + 2 * r + 5, y);
        sprite->setTextColor(TFT_CYAN, TFT_TRANSPARENT);
        sprite->drawString(units, x + 2 * r + 5, y + 18);
    
        sprite->loadFont(PFDFont25);
        sprite->setTextDatum(TR_DATUM);
        int text_width = sprite->textWidth("100.0") + 10;
        sprite->drawRect(x + 2 * r - text_width + 3, y + r + 7, text_width, sprite->fontHeight() + 10, 0xCE59);
        // sprite->fillRect(x + 2 * r - text_width + 3 + 1, y + r + 7 + 1, text_width - 2, sprite->fontHeight() + 10 - 2, TFT_BLACK);  // Uncomment to fill in rect bg
        if (current_value == -1) {
            sprite->setTextColor(TFT_AMBER, TFT_TRANSPARENT);
            sprite->drawString("XX", x + 2 * r, y + r + 13);
        } else {
            sprite->setTextColor(TFT_GREEN, TFT_TRANSPARENT);
            char buffer[6];
            sprintf(buffer, current_value < 10 ? "0%.1f" : "%.1f", current_value);
            sprite->drawString(buffer, x + 2 * r, y + r + 13);
        }
    }

    void create_lined_value(TFT_eSprite *sprite, int push_x, int push_y, const char* label, const char* units) {
        sprite->loadFont(PFDFont25);
        int value_w = sprite->textWidth("199.9");
        int value_h = sprite->fontHeight();
        // FE label and units
        sprite->setColorDepth(8);
        sprite->createSprite(value_w, value_h);
        sprite->fillSprite(TFT_BLACK);
        // FE label
        tft.loadFont(ECAMFont20);
        tft.setTextDatum(TC_DATUM);
        tft.setTextColor(TFT_WHITE, TFT_TRANSPARENT);
        tft.drawString(label, push_x + 2 * gauge_radius + 5, push_y);
        tft.setTextColor(TFT_CYAN, TFT_TRANSPARENT);
        tft.drawString(units, push_x + 2 * gauge_radius + 5, push_y + 18);
        // FE line
        tft.drawLine(push_x + value_w + 10, push_y + 12, push_x + 2 * gauge_radius - 18, push_y + 5, 0xCE59);
    }

    void update_lined_value(TFT_eSprite *sprite, const char* value, uint16_t color) {
        sprite->fillSprite(TFT_BLACK);
        sprite->loadFont(PFDFont25);
        sprite->setTextColor(color, TFT_TRANSPARENT);
        sprite->setTextDatum(TR_DATUM);
        sprite->drawString(value, sprite->width(), 0);
    }

    void update_direct_value(TFT_eSprite *sprite, const char* value, uint16_t color, const char* label, const char* units) {
        sprite->fillSprite(TFT_BLACK);
    
        // Label
        sprite->setTextDatum(TL_DATUM);
        sprite->loadFont(ECAMFont20);
        sprite->setTextColor(TFT_WHITE, TFT_TRANSPARENT);
        sprite->drawString(label, 0, 3);
        int text_x = sprite->textWidth(label) + 15;

        // Value
        sprite->loadFont(PFDFont25);
        sprite->setTextColor(color, TFT_TRANSPARENT);
        sprite->drawString(value, text_x, 0);
        text_x += sprite->textWidth(value) + 10;

        // Units
        if (units != NULL) {
            sprite->loadFont(ECAMFont20);
            sprite->setTextColor(TFT_CYAN, TFT_TRANSPARENT);
            sprite->drawString(units, text_x, 3);
        }
    }

    public:
    TFT_eSprite n1_gauge = TFT_eSprite(&tft);
    TFT_eSprite ff_disp = TFT_eSprite(&tft);
    // TFT_eSprite fe_disp = TFT_eSprite(&tft);
    TFT_eSprite location_disp = TFT_eSprite(&tft);
    TFT_eSprite evchrg_disp = TFT_eSprite(&tft);

    int push_x = speed_bar_w + engine_inst_lgap;
    int push_line_x = push_x;
    int push_dir_x = push_x + engine_inst_w + 40;
    int push_loc_x = push_x + engine_inst_w + 10;

    int push_n1_y = status_disp_h;
    int push_ff_y = 160;
    int push_fe_y = 50 + 45;
    int push_loc_y = status_disp_h + 4;
    int push_evchrg_y = 175;

    void setup() {
        n1_gauge.setColorDepth(8);
        n1_gauge.createSprite(engine_inst_w, gauge_height);
        n1_gauge.fillSprite(TFT_BLACK);

        create_lined_value(&ff_disp, push_line_x, push_ff_y, "F.F", "L/H");
        // create_lined_value(&fe_disp, push_line_x, push_fe_y, "F.E", "KM/L");
        
        location_disp.setColorDepth(8);
        location_disp.createSprite(480 - push_loc_x, 120);
        location_disp.fillSprite(TFT_BLACK);

        evchrg_disp.setColorDepth(8);
        evchrg_disp.createSprite(engine_inst_w, 25);
        evchrg_disp.fillSprite(TFT_BLACK);

        update(true);
    }

    void update(boolean force=false) {
        // RPM N1 Gauge
        const float smoothing = 0.1f;
        if (force || displayed_rpm != round(indicated_rpm * 10.0) / 10.0) {
            if (indicated_rpm == -1) {
                drawGauge(&n1_gauge, 5, 5, gauge_radius, 60, 270, 100, 100, -1, -1, 0, TFT_AMBER, "N1", "%");
            } else {
                if (abs(displayed_rpm - indicated_rpm) > 0.3f && displayed_rpm >= 0) {
                    new_displayed_rpm = displayed_rpm + (indicated_rpm - displayed_rpm) * smoothing;
                } else {
                    new_displayed_rpm = round(indicated_rpm * 10.0) / 10.0;
                }
                drawGauge(&n1_gauge, 5, 5, gauge_radius, 60, 270, (red_line_rpm / max_rpm) * 100, 100, (new_displayed_rpm / max_rpm) * 100, (displayed_rpm / max_rpm) * 100, (1000 / max_rpm) * 100, TFT_WHITE, "N1", "%");
            }
            n1_gauge.pushSprite(push_x, push_n1_y, TFT_TRANSPARENT);
            displayed_rpm = new_displayed_rpm;
            rerender_speedcam_popup = true;
        }
    
        // Fuel Flow Display
        if (force || displayed_ff != round(fuel_flow * 10.0) / 10.0) {
            if (force) create_lined_value(&ff_disp, push_line_x, push_ff_y, "F.F", "L/H");
            if (fuel_flow == -1) {
                update_lined_value(&ff_disp, "XX", TFT_AMBER);
            } else {
                char value_str[5];
                sprintf(value_str, "%.1f", fuel_flow);
                update_lined_value(&ff_disp, value_str, TFT_GREEN);
            }

            ff_disp.pushSprite(push_line_x, push_ff_y + 6, TFT_TRANSPARENT);
            displayed_ff = round(fuel_flow * 10.0) / 10.0;
            rerender_speedcam_popup = true;
        }

        // Fuel Efficiency Display
        // if (force || displayed_fe != round(fuel_efficiency * 10.0) / 10.0) {
        //     if (fuel_efficiency == -1) {
        //         update_lined_value(&fe_disp, "XX", TFT_AMBER);
        //     } else {
        //         char value_str[5];
        //         sprintf(value_str, "%.1f", fuel_efficiency);
        //         update_lined_value(&fe_disp, value_str, TFT_GREEN);
        //     }
            
        //     // fe_disp.pushSprite(push_line_x, push_fe_y + 6, TFT_TRANSPARENT);
        //     displayed_fe = round(fuel_efficiency * 10.0) / 10.0;
        // }

        // Location
        if (force || displayed_location_str != location_str) {
            location_disp.fillSprite(TFT_BLACK);
            location_disp.loadFont(ECAMFont20);
            location_disp.setTextDatum(TL_DATUM);

            location_str = vary + category + zoneReason + zoneName + zoneArea;

            location_disp.setTextColor(TFT_WHITE, TFT_TRANSPARENT);
            if (zoneReason == "" && zoneName == "" && zoneArea == "") {
                location_disp.drawString("No Location Data", 0, 40);
            } else {
                int y = 0;
                String zoneNameLower = zoneName;
                zoneNameLower.toLowerCase();
                String zoneAreaLower = zoneArea;
                zoneAreaLower.toLowerCase();
                String line4 = zoneNameLower.indexOf(zoneAreaLower) >= 0 ? "" : zoneArea;
                
                String rawLines[] = { vary, zoneReason, zoneName, line4 };
                int numLines = sizeof(rawLines) / sizeof(rawLines[0]);
                for (int i = 0; i < numLines; i++) {
                    if (rawLines[i].length() > 0) {  // Skip empty strings
                        std::vector<String> wrapped = wrapTextLines(location_disp, rawLines[i], location_disp.width());
                        for (size_t j = 0; j < wrapped.size(); j++) {
                            location_disp.drawString(wrapped[j], 0, y);
                            if (j == wrapped.size() - 1) {
                                // Last line of this raw line: apply 20px gap
                                y += 21;
                            } else {
                                // Wrapped lines within the same raw line: apply 16px gap
                                y += 17;
                            }
                        }
                    }
                }
            }
            
            location_disp.pushSprite(push_loc_x, push_loc_y, TFT_TRANSPARENT);
            displayed_location_str = location_str;
            rerender_speedcam_popup = true;
        }

        // EV Charge Display
        if (force || displayed_evchrg != int(round(ev_charge))) {
            if (ev_charge == -1) {
                update_direct_value(&evchrg_disp, "XX", TFT_AMBER, "CHRG:", "%");
            } else {
                update_direct_value(&evchrg_disp, String(int(round(ev_charge))).c_str(), TFT_GREEN, "CHRG:", "%");
            }
            evchrg_disp.pushSprite(push_dir_x, push_evchrg_y, TFT_TRANSPARENT);
            displayed_evchrg = int(round(ev_charge));
            rerender_speedcam_popup = true;
        }
    }
};


struct SubItem {
    String text;
    String right_aligned_text; // optional
    uint16_t color;
    int indent_level; // 0 or 1

    bool operator==(const SubItem& other) const {
        return text == other.text &&
               right_aligned_text == other.right_aligned_text &&
               color == other.color &&
               indent_level == other.indent_level;
    }

};

struct WarningItem {
    String main_heading;  // e.g., "ENG 1"
    String topic;  // e.g., "FAIL"
    uint16_t color;
    std::vector<SubItem> subitems;

    bool operator==(const WarningItem& other) const {
        return main_heading == other.main_heading &&
               topic == other.topic &&
               color == other.color &&
               subitems == other.subitems;
    }

};

void sortWarningsByColor(std::vector<WarningItem>& warnings);  // Must be defined here so auto-prototype generator won't create a conflicting one

std::vector<WarningItem> warnings;
std::vector<WarningItem> displayed_warnings;

void sortWarningsByColor(std::vector<WarningItem>& warnings) {
    std::stable_sort(warnings.begin(), warnings.end(), [](const WarningItem& a, const WarningItem& b) {
        auto getPriority = [](uint16_t color) {
            if (color == TFT_RED)   return 0;
            if (color == TFT_AMBER) return 1;
            return 2; // others
        };
        return getPriority(a.color) < getPriority(b.color);
    });
}

class WarningsDisplay {
    public:
    TFT_eSprite warning_disp = TFT_eSprite(&tft);

    void setup() {
        warning_disp.setColorDepth(8);
        warning_disp.createSprite(warning_disp_w, warning_disp_h);
        warning_disp.fillSprite(TFT_BLACK);

        update(true);
    }
    
    void update(boolean force=false) {
        if (force || rerender_speedcam_popup || displayed_warnings != warnings) {
            warning_disp.fillSprite(TFT_BLACK);
            warning_disp.loadFont(ECAMFont20);
            warning_disp.setTextDatum(TL_DATUM);
            
            int y_offset = 0;
            for (const auto& warning: warnings) {
                String full_title = warning.main_heading + " " + warning.topic;
                warning_disp.setTextColor(warning.color, TFT_TRANSPARENT);
                warning_disp.drawString(full_title, 0, y_offset);

                int heading_width = warning_disp.textWidth(warning.main_heading);
                warning_disp.drawFastHLine(0, y_offset + warning_disp.fontHeight() + 2, heading_width, warning.color);

                for (const auto& sub : warning.subitems) {
                    y_offset += 20;
                    int x_indent = sub.indent_level * 15;
                    
                    String left = sub.text;
                    String right = sub.right_aligned_text;
                    warning_disp.setTextColor(sub.color, TFT_TRANSPARENT);
                    if (right.length()) {
                        int total_width = warning_disp.textWidth(left + right);
                        int max_width = warning_disp_w - x_indent - 5;
                        int dots_needed = (max_width - total_width) / warning_disp.textWidth(". ");
                        String dots = "";
                        for (int i = 0; i < dots_needed; ++i) dots += ". ";
                        warning_disp.drawString(left + " " + dots + right, x_indent, y_offset);
                    } else {
                        warning_disp.drawString(left, x_indent, y_offset);
                    }

                }

                y_offset += 25;
            }
            
            warning_disp.pushSprite(warning_disp_x, warning_disp_y + 12, TFT_TRANSPARENT);
            displayed_warnings = warnings;
            rerender_speedcam_popup = false;
        }
    }
};


void sortMemosByColor(std::vector<std::pair<String, uint16_t>>& memos) {
    std::stable_sort(memos.begin(), memos.end(), [](const std::pair<String, uint16_t>& a, const std::pair<String, uint16_t>& b) {
        auto getPriority = [](uint16_t color) {
            if (color == TFT_RED)   return 0;
            if (color == TFT_AMBER) return 1;
            return 2; // others (green, cyan, etc.)
        };
        return getPriority(a.second) < getPriority(b.second);
    });
}

class MemosDisplay {
    public:
    TFT_eSprite memo_disp = TFT_eSprite(&tft);

    void setup() {
        memo_disp.setColorDepth(8);
        memo_disp.createSprite(memo_disp_w, memo_disp_h);
        memo_disp.fillSprite(TFT_BLACK);

        update(true);
    }
    
    void update(boolean force=false) {
        if (force || displayed_memos != memos) {
            memo_disp.fillSprite(TFT_BLACK);
            memo_disp.loadFont(ECAMFont20);
            memo_disp.setTextDatum(TL_DATUM);
            
            int y_offset = 0;
            for (const auto& memo: memos) {
                memo_disp.setTextColor(memo.second, TFT_TRANSPARENT);
                memo_disp.drawString(memo.first, 0, y_offset);
                y_offset += 20;
            }
            
            memo_disp.pushSprite(memo_disp_x, memo_disp_y + 12, TFT_TRANSPARENT);
            displayed_memos = memos;
        }
    }
};


class SpeedCamPopup {
    public:
    TFT_eSprite speedcam_popup = TFT_eSprite(&tft);

    void setup() {
        speedcam_popup.setColorDepth(8);
        speedcam_popup.createSprite(speedcam_disp_w, speedcam_disp_h);
        speedcam_popup.fillSprite(TFT_BLACK);
    }
    
    void update(boolean force=false) {
        boolean speedcamPopupVisible = speedCam_str != "" && speedCamDistance != -1;

        if (millis() - lastSpeedcamToggleTime >= 1000) {
            speedcamColourToggleState = !speedcamColourToggleState;
            lastSpeedcamToggleTime = millis();
            if (speedcamPopupVisible) {
                force = true;
                // Serial.println("Forcing speedcam update");
            }
        }

        if (force || (speedcamPopupVisible && 
            (displayed_speedCam_str != speedCam_str || displayed_speedCamDistance != speedCamDistance))) {
            // Serial.println("Speed cam popup updated: " + speedCam_str);

            uint16_t backgroundColor = (speedcamAlertMode && speedcamColourToggleState) ? DARK_RED : TFT_BLACK;
            uint16_t outerBorderColor = speedcamColourToggleState ? GREY_RED : TFT_GREY;
            uint16_t innerBorderColor = speedcamColourToggleState ? LIGHT_RED : TFT_WHITE;

            speedcam_popup.fillRect(10, 10, speedcam_disp_w - 10, speedcam_disp_h - 10, outerBorderColor);  // Outer border
            speedcam_popup.fillRect(12, 12, speedcam_disp_w - 14, speedcam_disp_h - 14, TFT_BLACK);  // Outer background
            speedcam_popup.fillRect(0, 0, speedcam_disp_w - 10, speedcam_disp_h - 10, innerBorderColor);  // Inner border
            speedcam_popup.fillRect(2, 2, speedcam_disp_w - 14, speedcam_disp_h - 14, backgroundColor);  // Inner background

            speedcam_popup.loadFont(ECAMFont20);
            speedcam_popup.setTextColor(TFT_WHITE, backgroundColor);
            speedcam_popup.setTextDatum(TL_DATUM);

            int y = 10;         
            String rawLines[] = { speedCamDescription, speedCamStreet, speedCamSuburb, speedCamLocation };
            int numLines = sizeof(rawLines) / sizeof(rawLines[0]);
            for (int i = 0; i < numLines; i++) {
                String temp = rawLines[i];
                temp.toLowerCase();
                if (rawLines[i].length() > 0 && temp != "none") {  // Skip empty strings
                    std::vector<String> wrapped = wrapTextLines(speedcam_popup, rawLines[i], speedcam_popup.width() - 30);
                    for (size_t j = 0; j < wrapped.size(); j++) {
                        speedcam_popup.drawString(wrapped[j], 10, y);
                        if (j == wrapped.size() - 1) {
                            // Last line of this raw line: apply 20px gap
                            y += 21;
                            if (i == 0) {y += 7;}  // Add gap after description
                        } else {
                            // Wrapped lines within the same raw line: apply 16px gap
                            y += 17;
                        }
                    }
                }
            }

            speedcam_popup.setTextDatum(BR_DATUM);
            speedcam_popup.drawString("m", speedcam_disp_w - 16, speedcam_disp_h - 16);
            speedcam_popup.loadFont(PFDFont25);
            speedcam_popup.drawString(String(int(speedCamDistance)), speedcam_disp_w - 18 - 15, speedcam_disp_h - 14);
            
            speedcam_popup.pushSprite(speedcam_disp_x, speedcam_disp_y, TFT_TRANSPARENT);
        }
        displayed_speedCam_str = speedCam_str;
        displayed_speedCamDistance = speedCamDistance;
    }

    void clear() {
        speedcam_popup.fillSprite(TFT_BLACK);
        speedcam_popup.pushSprite(speedcam_disp_x, speedcam_disp_y, TFT_TRANSPARENT);
    }
};


struct BuzzerStep {
    unsigned int frequency;  // tone frequency in Hz (0 = silence)
    unsigned long duration;  // step duration in ms
};
void startBuzzerPattern(const BuzzerStep* pattern, int count);  // Must be defined here so auto-prototype generator won't create a conflicting one

BuzzerStep buzzerPattern[MAX_BUZZER_STEPS];

void handleBuzzer() {
    if (!buzzerActive) return;

    unsigned long now = millis();
    if (now - buzzerStepStart >= buzzerPattern[buzzerCurrentStep].duration) {
        buzzerCurrentStep++;
        buzzerStepStart = now;

        if (buzzerCurrentStep >= buzzerStepCount) {
            // End of sequence
            noTone(BUZZER_PIN);
            buzzerActive = false;
            return;
        }

        // Play next step
        unsigned int freq = buzzerPattern[buzzerCurrentStep].frequency;
        if (freq > 0) tone(BUZZER_PIN, freq);
        else noTone(BUZZER_PIN);
    }
}

void startBuzzerPattern(const BuzzerStep* pattern, int count) {
    for (int i = 0; i < count && i < MAX_BUZZER_STEPS; i++) {
        buzzerPattern[i] = pattern[i];
    }
    buzzerStepCount = count;
    buzzerCurrentStep = 0;
    buzzerStepStart = millis();
    buzzerActive = true;

    // Start first tone immediately
    if (buzzerPattern[0].frequency > 0)
        tone(BUZZER_PIN, buzzerPattern[0].frequency);
    else
        noTone(BUZZER_PIN);
}

const BuzzerStep speedCamBzPattern[] = {
    {1750, 250}, {0, 50}, {1000, 250}, {0, 50}, {1750, 250}, {0, 50}, {1000, 250}, {0, 50}
};

const BuzzerStep overspeedBzPattern[] = {
    {1750, 200}, {0, 100}, {1750, 200}, {0, 100}, {1750, 200}
};

const BuzzerStep connLostBzPattern[] = {
    {800, 1000}
};



bool isValidNumber(String str) {
    bool seenDecimal = false;
    int len = str.length();

    if (len == 0) return false;

    int i = 0;
    // Check optional leading sign
    if (str[i] == '+' || str[i] == '-') {
        i++;
    }

    bool hasDigits = false;
    
    for (; i < len; i++) {
        char c = str[i];
        if (isDigit(c)) {
            hasDigits = true;
        } else if (c == '.' && !seenDecimal) {
            seenDecimal = true;
        } else {
            return false; // invalid character
        }
    }

    return hasDigits;
}


void parseData(String packet) {
    lastDataTime = millis();

    packet = packet.substring(1, packet.length() - 1);
    while (packet.length()) {
        int comma = packet.indexOf(',');
        String pair = (comma == -1) ? packet : packet.substring(0, comma);

        int sep = pair.indexOf(':');
        if (sep > 0) {
            String key = pair.substring(0, sep);
            String value = pair.substring(sep + 1);
            saveData(key, value);
        }

        if (comma == -1) break;
        packet = packet.substring(comma + 1);
    }
}


void parseSpeedCam(String value) {
    speedCamDescription = "";
    speedCamStreet = "";
    speedCamSuburb = "";
    speedCamLocation = "";
    
    value = value.substring(1, value.length() - 1);
    
    int start = 0;
    while (start < value.length()) {
        int sep = value.indexOf(';', start);
        String pair = (sep == -1) ? value.substring(start) : value.substring(start, sep);
        int eq = pair.indexOf('=');
        if (eq > 0) {
            String camKey = pair.substring(0, eq);
            String camVal = pair.substring(eq + 1);
            // Serial.println("  " + camKey + ": " + camVal);

            // You can now assign to a struct or variables as needed
            if (camKey == "description") speedCamDescription = camVal;
            else if (camKey == "street") speedCamStreet = camVal;
            else if (camKey == "suburb") speedCamSuburb = camVal;
            else if (camKey == "location") speedCamLocation = camVal;
            else if (camKey == "distance") speedCamDistance = camVal.toFloat();
        }

        if (sep == -1) break;
        start = sep + 1;
    }

    speedCam_str = speedCamDescription + speedCamStreet + speedCamSuburb + speedCamLocation;
    if (speedCam_str == "" && speedCamDistance != -1) {
        speedCamDistance = -1;
        // Serial.println("Speed cam cleared");
    }
}


void saveData(String key, String value) {
    if (value == "None") value = "";
    // Serial.println(key + " " + value);
    if (key == "ASPD") {if (isValidNumber(value)) {indicated_speed = value.toFloat();} else {indicated_speed = -1;}}
    if (key == "SPDSRC") {speed_source = value;}
    if (key == "SPDPRD") {if (isValidNumber(value)) {speed_prediction = value.toInt();} else {speed_prediction = -999;}}
    // if (key == "WSPD") {if (speed_source == "W") {if (isValidNumber(value)) {indicated_speed = value.toInt();} else {indicated_speed = -1;}}}
    // if (key == "GSPD") {if (speed_source == "G") {if (isValidNumber(value)) {indicated_speed = value.toInt();} else {indicated_speed = -1;}}}
    // if (key == "CSPD") {if (speed_source == "C") {if (isValidNumber(value)) {indicated_speed = value.toInt();} else {indicated_speed = -1;}}}
    if (key == "RPM") {if (isValidNumber(value)) {indicated_rpm = value.toInt();} else {indicated_rpm = -1;}}
    if (key == "FUELFLOW") {if (isValidNumber(value)) {fuel_flow = value.toFloat();} else {fuel_flow = -1;}}
    if (key == "BATREM") {if (isValidNumber(value)) {ev_charge = value.toInt();} else {ev_charge = -1;}}
    if (key == "CARCON") {if (isValidNumber(value)) {if (value.toInt() == 1) {car_connected = true;} else {car_connected = false;}}}
    if (key == "MODCON") {if (isValidNumber(value)) {if (value.toInt() == 1) {gps_module_connected = true;} else {gps_module_connected = false;}}}
    if (key == "SGNL") {if (isValidNumber(value)) {if (value.toInt() == 1) {gps_signal = true;} else {gps_signal = false;}}}
    if (key == "NUMSATS") {if (isValidNumber(value)) {num_sats = value.toInt();}}
    if (key == "WIFI") {if (isValidNumber(value)) {if (value.toInt() == 1) {wifi = true;} else {wifi = false;}}}
    if (key == "TIME") {current_time = value;}
    if (key == "DATE") {current_date = value;}
    if (key == "LIM") {if (isValidNumber(value)) {max_speed = value.toInt(); if (max_speed == -1) max_speed = 100;}}
    if (key == "VARY") {vary = value;}
    if (key == "CATEGORY") {category = value;}
    if (key == "ZONEREASON") {zoneReason = value;}
    if (key == "ZONENAME") {zoneName = value;}
    if (key == "ZONEAREA") {zoneArea = value;}
    if (key == "SPEEDCAM") {parseSpeedCam(value);}

    location_str = vary + category + zoneReason + zoneName + zoneArea;
}




SpeedBar speed_bar;
StatusDisplay status_disp;
EngineInstruments engine_instruments;
WarningsDisplay warning_disp;
MemosDisplay memo_disp;
SpeedCamPopup speedcam_popup;


void setup() {
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);

    pinMode(BL_PIN, OUTPUT);
    Serial.begin(115200); // For debug
    
    tft.init();
    tft.setRotation(1);
    
    tft.fillScreen(TFT_BLACK);
    tft.loadFont(ECAMFont20);
    tft.setTextColor(TFT_GREEN, TFT_TRANSPARENT);
    tft.setTextDatum(BC_DATUM);
    tft.drawString(F("SELF TEST IN PROGRESS"), 480 / 2, 320 / 2 - 5);
    tft.setTextDatum(TC_DATUM);
    tft.drawString(F("(MAX 40 SECONDS)"), 480 / 2, 320 / 2 + 5);
    
    tft.unloadFont();
    tft.setTextFont(1);
    tft.setTextSize(1);
    tft.setTextDatum(TR_DATUM);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    
    delay(100);
    digitalWrite(BL_PIN, HIGH);

    char info[50];
    int usedStat;
    int maxStat;
    int usedPercentage;
    
    usedStat = ESP.getSketchSize();
    maxStat = ESP.getFlashChipSize();
    usedPercentage = (usedStat * 100) / maxStat;
    sprintf(info, "FLASH: %d/%d (%d%%)", usedStat, maxStat, usedPercentage);
    tft.drawString(info, 480, 0);

    Serial1.begin(9600, SERIAL_8N1, RXD1, TXD1);
    delay(2500);

    while (millis() < 40000) {
        if (Serial1.available()) {
            break;
        }
        delay(100);
    }

    tft.fillScreen(TFT_BLACK);

    speed_bar.setup();
    status_disp.setup();
    engine_instruments.setup();
    warning_disp.setup();
    memo_disp.setup();
    speedcam_popup.setup();

    tft.fillRect(warning_disp_x, warning_disp_y, warning_disp_w - 5, line_w, TFT_WHITE);
    tft.fillRect(memo_disp_x, memo_disp_y, memo_disp_w, line_w, TFT_WHITE);

    tft.fillRect(memo_disp_x - 15, memo_disp_y + 10, line_w, warning_disp_w, TFT_WHITE);

    tft.unloadFont();
    tft.setTextFont(1);
    tft.setTextSize(1);
    tft.setTextDatum(TR_DATUM);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
}


#define ARRAY_SIZE 20
unsigned long timeTakenArray[ARRAY_SIZE] = {0};  // Array to store loop times
int timeIndex = 0;  // Index for circular buffer
int timeCount = 0;  // Count of stored values


void loop() {
    static String buffer = "";

    while (Serial1.available()) {
        char c = Serial1.read();

        if (c == '<') {
            buffer = "";  // Start of new message
        }

        buffer += c;

        if (c == '>') {
            test_mode = false;
            parseData(buffer);
            buffer = "";  // Reset for next message
        }
    }

    if (updateTime <= millis()) {
        updateTime = millis() + 25;
        unsigned long startTime = millis();
        

        warnings.clear();
        memos.clear();
        
        if (millis() > 15000 && test_mode) {
            int max_test_speed = 140;
            int test_speed = 5000;
            indicated_speed = (sin(millis() * PI / test_speed) + 1) * (max_test_speed/2);
            indicated_rpm = max(853.0, cos(millis() * PI / test_speed) * max_rpm * 1.05);
    
            wifi = true;
            num_sats = 10;
    
            fuel_flow = max(0.0, cos(millis() * PI / test_speed) * 20);
            fuel_efficiency = 29.8 - sin(millis() * PI / test_speed) * 2.3 * pow(0.99, millis() / 1000);
            ev_charge = 60 - sin(millis() * PI / test_speed) * 21;

            // ALTN LAW: PROT LOST       (GREEN)
            memos.push_back({"IGNITION", TFT_GREEN});
            memos.push_back({"PARK BRK", TFT_GREEN});
            memos.push_back({"SEAT BELT NOT ENG", TFT_RED});
        }
        

        if (!test_mode && millis() - lastDataTime > 5000) {
            warnings.push_back({"DATA", "CONN FAIL", TFT_RED, {{"- DEV POWER", "CHECK", TFT_CYAN, 1}, {"- SERVICE", "START", TFT_CYAN, 1}}});
        } else if (!test_mode && gps_module_connected == false) {
            warnings.push_back({"GPS", "CONN FAIL", TFT_RED, {{"- GPS CONN", "CHECK", TFT_CYAN, 1}}});
        } else if (!test_mode && gps_signal == false) {
            warnings.push_back({"GPS", "NO SIGNAL", TFT_RED, {}});
            if (car_connected) {
                memos.push_back({"DIR LAW: PROT LOST", TFT_GREEN});
            }
        } else if (num_sats <= 6) {
            warnings.push_back({"GPS", "UNRELIABLE", TFT_AMBER, {}});
            if (car_connected) {
                memos.push_back({"ALTN LAW: PROT LOST", TFT_GREEN});
            } else {
                memos.push_back({"DIR LAW: PROT LOST", TFT_GREEN});
            }
        } else if (!car_connected) {
            memos.push_back({"ALTN LAW: PROT LOST", TFT_GREEN});
        }

        speedcamAlertMode = false;
        if (indicated_speed == -1) {
            memos.push_back({"SPEED UNAVAIL", TFT_RED});
        } else if (indicated_speed > max_speed + overspeed_red_speed) {
            warnings.push_back({"OVERSPEED", "", TFT_RED, {{"- MAX SPD", String(max_speed) + "KM/H", TFT_CYAN, 1}}});
            speedcamAlertMode = true;
            if (prev_overspeeding == false) {
                prev_overspeeding = true;
                startBuzzerPattern(overspeedBzPattern, sizeof(overspeedBzPattern) / sizeof(BuzzerStep));
            }
        } else if (indicated_speed > max_speed) {
            warnings.push_back({"OVERSPEED", "", TFT_AMBER, {{"- MAX SPD", String(max_speed) + "KM/H", TFT_CYAN, 1}}});
            speedcamAlertMode = true;
        } else {
            prev_overspeeding = false;
        }

        if (indicated_rpm == -1) {
            memos.push_back({"RPM UNAVAIL", TFT_AMBER});
        } else if (indicated_rpm > max_rpm) {
            warnings.push_back({"N1", "OVER LIMIT", TFT_RED, {{"- THR", "IDLE", TFT_CYAN, 1}}});
        } else if (indicated_rpm > red_line_rpm) {
            warnings.push_back({"N1", "RED LINE", TFT_AMBER, {{"- THR", "REDUCE", TFT_CYAN, 1}}});
        }

        if (ev_charge == -1) {}
        else if (ev_charge < 40 && ev_charge > 0) {
            warnings.push_back({"EV BAT", "UNDER VOLTAGE", TFT_AMBER, {}});
        } else if (ev_charge > 80) {
            warnings.push_back({"EV BAT", "OVER VOLTAGE", TFT_AMBER, {}});
        }

        if (wifi) {
            memos.push_back({"SSH READY", TFT_GREEN});
        }


        if (displayed_speedCam_str != speedCam_str && speedCam_str != "") {
            startBuzzerPattern(speedCamBzPattern, sizeof(speedCamBzPattern) / sizeof(BuzzerStep));
        }

        handleBuzzer();

        sortWarningsByColor(warnings);
        sortMemosByColor(memos);

        speed_bar.update();
        status_disp.update();
        if (speedCam_str == "") {
            if (displayed_speedCam_str.length() > 0) {
                speedcam_popup.clear();
                engine_instruments.update(true);
            } else {
                engine_instruments.update();
            }
        }
        warning_disp.update();
        memo_disp.update();
        speedcam_popup.update();



        unsigned long loopTime = millis() - startTime;
        timeTakenArray[timeIndex] = loopTime;
        timeIndex = (timeIndex + 1) % ARRAY_SIZE;
        if (timeCount < ARRAY_SIZE) {
            timeCount++;
        }
        unsigned long maxTime = 0;
        unsigned long total = 0;
        for (int i = 0; i < timeCount; i++) {
            total += timeTakenArray[i];
            if (timeTakenArray[i] > maxTime) {maxTime = timeTakenArray[i];}
        }
        float avgTime = total / (float)timeCount;

        // Serial.print("Last loop time: ");
        // Serial.println(loopTime);

        tft.unloadFont();

        char info[50];
        // sprintf(info, "LPt: %dms | %dms max (%d fps)", (int)round(avgTime), (int)round(maxTime), (int)min(99.0, round(1000.0 / avgTime)));
        // tft.drawString(info, 480, 10);
        // sprintf(info, "Run t: %dm %ds", (int)round(millis() / 60000), (int)round((millis() / 1000) % 60));
        // tft.drawString(info, 480, 20);

        int usedStat;
        int maxStat;
        int usedPercentage;
        usedStat = ESP.getHeapSize() - ESP.getFreeHeap();
        maxStat = ESP.getHeapSize();
        usedPercentage = (usedStat * 100) / maxStat;
        // sprintf(info, "RAM: %d/%d (%d%%)", usedStat, maxStat, usedPercentage);
        // tft.drawString(info, 480, 0);

        sprintf(info, "%dm %02ds | RAM %d%% | %02d fps", (int)round(millis() / 60000), (int)round((millis() / 1000) % 60), usedPercentage, (int)min(99.0, round(1000.0 / avgTime)));
        // tft.fillRect(memo_disp_x, 310, 480 - memo_disp_x, 10, TFT_BLACK);
        tft.drawString(info, 480, 310);
    }
}
