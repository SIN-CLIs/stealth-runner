// mac_eye.h – Shared Memory Ringbuffer für Framebuffer-Daten
#ifndef MAC_EYE_H
#define MAC_EYE_H

#include <stdint.h>
#include <stdatomic.h>

#define MAC_EYE_SHM_NAME    "/mac_eye_framebuffer"
#define MAC_EYE_MAX_FRAMES  4
#define MAC_EYE_WIDTH       1920
#define MAC_EYE_HEIGHT      1080
#define MAC_EYE_MAX_DEVICES 256

typedef struct __attribute__((packed)) {
    _Atomic uint64_t   timestamp_ns;
    _Atomic uint32_t   frame_index;
    _Atomic uint32_t   width;
    _Atomic uint32_t   height;
    _Atomic uint32_t   bytes_per_row;
    _Atomic uint32_t   pixel_format;
    _Atomic uint8_t    dirty;
    uint8_t            _pad[3];
    uint8_t            data[MAC_EYE_WIDTH * MAC_EYE_HEIGHT * 4];
} MacEyeFrame;

typedef struct __attribute__((packed)) {
    _Atomic uint32_t   magic;
    _Atomic uint32_t   version;
    _Atomic uint32_t   write_index;
    _Atomic uint32_t   read_index;
    _Atomic uint64_t   total_frames;
    _Atomic uint64_t   total_dropped;
    _Atomic int32_t    target_pid;
    _Atomic uint64_t   display_id;
    _Atomic int16_t    mouse_x;
    _Atomic int16_t    mouse_y;
    _Atomic uint8_t    running;
    uint8_t            _pad2[7];
    MacEyeFrame        frames[MAC_EYE_MAX_FRAMES];
} MacEyeSharedMemory;

#endif
