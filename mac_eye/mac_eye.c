// mac_eye.c – DYLD-Library, injected in Chrome via DYLD_INSERT_LIBRARIES
// Nutzt private Apple-Frameworks: IOSurface, CGSConnection, SkyLight
// NUR mit SIP=off (Recovery Mode) moeglich.
//
// Build:
//   clang -dynamiclib -framework Foundation -framework CoreGraphics
//         -framework IOSurface -framework SkyLight -framework IOKit
//         -F /System/Library/PrivateFrameworks
//         -o mac_eye.dylib mac_eye.c

#include "mac_eye.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <mach/mach.h>
#include <mach/mach_time.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <CoreGraphics/CoreGraphics.h>

typedef int CGSConnectionID;
extern CGSConnectionID CGSMainConnectionID(void);

typedef struct __IOSurface *IOSurfaceRef;
extern IOSurfaceRef IOSurfaceLookup(uint32_t surfaceID);
extern kern_return_t IOSurfaceLock(IOSurfaceRef surface, uint32_t options, uint32_t *seed);
extern kern_return_t IOSurfaceUnlock(IOSurfaceRef surface, uint32_t options, uint32_t *seed);
extern void *IOSurfaceGetBaseAddress(IOSurfaceRef surface);
extern size_t IOSurfaceGetBytesPerRow(IOSurfaceRef surface);

extern void SLEventPostToPid(int pid, void *event);

static MacEyeSharedMemory *g_shm = NULL;
static int g_shm_fd = -1;
static pthread_t g_capture_thread;
static volatile int g_running = 1;

static inline uint64_t nanotime(void) {
    static mach_timebase_info_data_t tb = {0};
    if (tb.denom == 0) mach_timebase_info(&tb);
    uint64_t now = mach_absolute_time();
    return now * tb.numer / tb.denom;
}

__attribute__((constructor))
static void mac_eye_init(void) {
    if (!getenv("MAC_EYE_ENABLE")) return;
    fprintf(stderr, "[mac_eye] Initialisiere Shared Memory...\n");

    int fd = shm_open(MAC_EYE_SHM_NAME, O_CREAT | O_RDWR, 0600);
    if (fd < 0) { perror("[mac_eye] shm_open"); return; }

    size_t sz = sizeof(MacEyeSharedMemory);
    if (ftruncate(fd, sz) < 0) { perror("[mac_eye] ftruncate"); close(fd); return; }

    void *ptr = mmap(NULL, sz, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (ptr == MAP_FAILED) { perror("[mac_eye] mmap"); close(fd); return; }

    g_shm_fd = fd;
    g_shm = (MacEyeSharedMemory *)ptr;

    if (atomic_load(&g_shm->magic) != 0x4D414345) {
        memset(g_shm, 0, sz);
        atomic_store(&g_shm->magic, 0x4D414345);
        atomic_store(&g_shm->version, 1);
        atomic_store(&g_shm->target_pid, (int32_t)getpid());
        atomic_store(&g_shm->display_id, (uint64_t)CGMainDisplayID());
        atomic_store(&g_shm->running, 1);
    }

    fprintf(stderr, "[mac_eye] Shared Memory bereit @ %p (PID=%d)\n", g_shm, getpid());
}

__attribute__((destructor))
static void mac_eye_cleanup(void) {
    g_running = 0;
    if (g_capture_thread) pthread_join(g_capture_thread, NULL);
    if (g_shm) { atomic_store(&g_shm->running, 0); munmap(g_shm, sizeof(MacEyeSharedMemory)); g_shm = NULL; }
    if (g_shm_fd >= 0) { close(g_shm_fd); g_shm_fd = -1; }
}

static void *capture_loop(void *arg) {
    (void)arg;
    CGDirectDisplayID displayID = (CGDirectDisplayID)atomic_load(&g_shm->display_id);
    uint32_t frame_counter = 0;
    fprintf(stderr, "[mac_eye] Capture-Loop gestartet\n");

    while (atomic_load(&g_shm->running) && g_running) {
        uint64_t t0 = nanotime();
        CGImageRef img = CGDisplayCreateImage(displayID);
        if (!img) { usleep(16666); continue; }

        CGDataProviderRef provider = CGImageGetDataProvider(img);
        CFDataRef data = CGDataProviderCopyData(provider);
        if (!data) { CGImageRelease(img); usleep(16666); continue; }

        size_t width = CGImageGetWidth(img), height = CGImageGetHeight(img);
        size_t bpr = CGImageGetBytesPerRow(img), dataLen = CFDataGetLength(data);

        uint32_t write_idx = atomic_load(&g_shm->write_index);
        uint32_t next_idx = (write_idx + 1) % MAC_EYE_MAX_FRAMES;
        if (next_idx == atomic_load(&g_shm->read_index)) {
            atomic_fetch_add(&g_shm->total_dropped, 1);
            CFRelease(data); CGImageRelease(img); usleep(1); continue;
        }

        MacEyeFrame *frame = &g_shm->frames[write_idx];
        size_t copy_len = dataLen < sizeof(frame->data) ? dataLen : sizeof(frame->data);
        memcpy(frame->data, CFDataGetBytePtr(data), copy_len);
        atomic_store(&frame->timestamp_ns, t0);
        atomic_store(&frame->frame_index, ++frame_counter);
        atomic_store(&frame->width, (uint32_t)width);
        atomic_store(&frame->height, (uint32_t)height);
        atomic_store(&frame->bytes_per_row, (uint32_t)bpr);
        atomic_store(&frame->pixel_format, (uint32_t)0x42475241); // BGRA
        atomic_store(&frame->dirty, 1);
        atomic_store(&g_shm->write_index, next_idx);
        atomic_fetch_add(&g_shm->total_frames, 1);

        CFRelease(data); CGImageRelease(img);
        uint64_t elapsed = nanotime() - t0;
        if (elapsed < 16666666) usleep((16666666 - elapsed) / 1000);
    }
    return NULL;
}

__attribute__((visibility("default")))
int mac_eye_start_capture(void) {
    if (!g_shm || atomic_load(&g_shm->magic) != 0x4D414345) return -1;
    atomic_store(&g_shm->running, 1); g_running = 1;
    if (pthread_create(&g_capture_thread, NULL, capture_loop, NULL) != 0) return -2;
    return 0;
}

__attribute__((visibility("default")))
int mac_eye_stop_capture(void) { g_running = 0; if (g_shm) atomic_store(&g_shm->running, 0); return 0; }

__attribute__((visibility("default")))
MacEyeSharedMemory *mac_eye_get_shm(void) { return g_shm; }
