/*
 * Run a lighting tool that predates the luminance lightmap layout on a script
 * that asks for it.
 *
 * Deadlock's compiler writes version 5 scripts, which consolidate the r, g and
 * b directional channels into one luminance channel. Released vrad3 builds lack
 * the two commands that do this. This wrapper rewrites them into the four-file
 * sh2 write those builds have, runs the real tool (vrad3_base.exe beside it),
 * and then derives the luminance file from the four outputs.
 *
 * Each sh2 file is an uncompressed EXR of three half channels (B, G, R). The
 * dc file holds linear L0 per color; each directional file holds that color's
 * L1/L0 vector encoded as 0.5 + 0.5 * v. The luminance file holds the same
 * encoding of the luminance-weighted vector sum(w * L1) / sum(w * L0).
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_PAIRS 16

static const char *const color_suffix[3] = {"_r", "_g", "_b"};
static const float luminance_weight[3] = {0.2126f, 0.7152f, 0.0722f};

typedef struct {
    char dc[MAX_PATH];
    char lum[MAX_PATH];
    char color[3][MAX_PATH];
} Sh2Pair;

static float half_to_float(unsigned short h)
{
    unsigned sign = (h >> 15) & 1, exponent = (h >> 10) & 31, mantissa = h & 1023;
    float value;
    if (exponent == 0)
        value = ldexpf((float)mantissa, -24);
    else if (exponent == 31)
        value = mantissa ? NAN : INFINITY;
    else
        value = ldexpf((float)(mantissa | 1024), (int)exponent - 25);
    return sign ? -value : value;
}

static unsigned short float_to_half(float f)
{
    unsigned bits;
    memcpy(&bits, &f, sizeof(bits));
    unsigned sign = (bits >> 16) & 0x8000;
    int exponent = (int)((bits >> 23) & 255) - 127 + 15;
    unsigned mantissa = bits & 0x7fffff;
    if (exponent <= 0)
        return (unsigned short)sign;
    if (exponent >= 31)
        return (unsigned short)(sign | 0x7c00);
    unsigned half = sign | ((unsigned)exponent << 10) | (mantissa >> 13);
    if (mantissa & 0x1000)
        half++; /* round half up; carries into the exponent correctly */
    return (unsigned short)half;
}

static unsigned char *read_file(const char *path, size_t *size)
{
    FILE *file = fopen(path, "rb");
    if (file == NULL)
        return NULL;
    fseek(file, 0, SEEK_END);
    long length = ftell(file);
    fseek(file, 0, SEEK_SET);
    unsigned char *data = malloc((size_t)length);
    if (data != NULL && fread(data, 1, (size_t)length, file) != (size_t)length) {
        free(data);
        data = NULL;
    }
    fclose(file);
    *size = (size_t)length;
    return data;
}

static int read_i32(const unsigned char *p)
{
    int value;
    memcpy(&value, p, sizeof(value));
    return value;
}

/*
 * Locate the pixel rows of an uncompressed scanline EXR with three half
 * channels. Returns the offset of the first row's header and the image size.
 */
static int exr_layout(const unsigned char *data, size_t size, size_t *rows, int *width, int *height)
{
    if (size < 8 || read_i32(data) != 20000630)
        return 0;
    size_t i = 8;
    int found_window = 0, found_compression = 0;
    while (i < size && data[i] != 0) {
        const char *name = (const char *)data + i;
        i += strlen(name) + 1;
        const char *type = (const char *)data + i;
        i += strlen(type) + 1;
        int length = read_i32(data + i);
        i += 4;
        if (strcmp(name, "dataWindow") == 0) {
            *width = read_i32(data + i + 8) - read_i32(data + i) + 1;
            *height = read_i32(data + i + 12) - read_i32(data + i + 4) + 1;
            found_window = 1;
        } else if (strcmp(name, "compression") == 0) {
            if (data[i] != 0)
                return 0;
            found_compression = 1;
        }
        i += (size_t)length;
    }
    i += 1 + 8 * (size_t)*height;
    size_t row_bytes = 8 + 3 * 2 * (size_t)*width;
    if (!found_window || !found_compression || i + row_bytes * (size_t)*height > size)
        return 0;
    *rows = i;
    return 1;
}

static int write_luminance(const Sh2Pair *pair)
{
    unsigned char *files[4];
    size_t sizes[4], rows[4];
    int width[4], height[4], ok = 1;
    const char *paths[4] = {pair->dc, pair->color[0], pair->color[1], pair->color[2]};
    for (int f = 0; f < 4; f++) {
        files[f] = read_file(paths[f], &sizes[f]);
        if (files[f] == NULL || !exr_layout(files[f], sizes[f], &rows[f], &width[f], &height[f])) {
            fprintf(stderr, "vrad3 shim: cannot read %s\n", paths[f]);
            ok = 0;
        } else if (width[f] != width[0] || height[f] != height[0]) {
            fprintf(stderr, "vrad3 shim: %s differs in size from %s\n", paths[f], paths[0]);
            ok = 0;
        }
    }
    if (ok) {
        /* The output reuses the red file's header and row layout. */
        unsigned char *out = files[1];
        int w = width[0];
        for (int y = 0; y < height[0]; y++) {
            unsigned short *row[4];
            for (int f = 0; f < 4; f++)
                row[f] = (unsigned short *)(files[f] + rows[f] + (size_t)y * (8 + 6 * (size_t)w) + 8);
            for (int x = 0; x < w; x++) {
                float weight_sum = 0, axis[3] = {0, 0, 0};
                for (int c = 0; c < 3; c++) {
                    /* Channels are stored B, G, R; color c is R, G, B. */
                    float l0 = half_to_float(row[0][(2 - c) * w + x]);
                    float weight = luminance_weight[c] * (l0 > 0 ? l0 : 0);
                    weight_sum += weight;
                    for (int a = 0; a < 3; a++)
                        axis[a] += weight * (2 * half_to_float(row[1 + c][a * w + x]) - 1);
                }
                for (int a = 0; a < 3; a++) {
                    float v = weight_sum > 0 ? axis[a] / weight_sum : 0;
                    ((unsigned short *)(out + rows[1] + (size_t)y * (8 + 6 * (size_t)w) + 8))[a * w + x] =
                        float_to_half(0.5f + 0.5f * v);
                }
            }
        }
        FILE *file = fopen(pair->lum, "wb");
        ok = file != NULL && fwrite(out, 1, sizes[1], file) == sizes[1];
        if (file != NULL)
            ok = fclose(file) == 0 && ok;
        if (!ok)
            fprintf(stderr, "vrad3 shim: cannot write %s\n", pair->lum);
    }
    for (int f = 0; f < 4; f++)
        free(files[f]);
    for (int c = 0; ok && c < 3; c++)
        DeleteFileA(pair->color[c]);
    return ok;
}

/* Copy the next whitespace-separated token of line into out. */
static const char *next_token(const char *line, char *out, size_t size)
{
    while (*line == ' ' || *line == '\t')
        line++;
    size_t n = 0;
    while (*line && *line != ' ' && *line != '\t' && *line != '\r' && *line != '\n') {
        if (n + 1 < size)
            out[n++] = *line;
        line++;
    }
    out[n] = '\0';
    return line;
}

/*
 * Rewrite script into shim_script. Fills pairs with each dc and luminance file
 * the script asked for and returns how many, or -1 when the script cannot be
 * read or written.
 */
static int rewrite_script(const char *script, const char *shim_script, Sh2Pair *pairs)
{
    FILE *in = fopen(script, "rb");
    if (in == NULL)
        return -1;
    FILE *out = fopen(shim_script, "wb");
    if (out == NULL) {
        fclose(in);
        return -1;
    }
    int count = 0;
    char line[4096], command[256], arg[MAX_PATH], extra[MAX_PATH];
    while (fgets(line, sizeof(line), in)) {
        const char *rest = next_token(line, command, sizeof(command));
        if (strcmp(command, "lightmap_image_consolidate_sh2_directional") == 0)
            continue;
        if (strcmp(command, "lightmap_image_write_sh2_lum") == 0) {
            next_token(rest, arg, sizeof(arg));
            if (count > 0)
                snprintf(pairs[count - 1].lum, MAX_PATH, "%s", arg);
            continue;
        }
        if (strcmp(command, "lightmap_image_write_sh2") == 0 && count < MAX_PAIRS) {
            rest = next_token(rest, arg, sizeof(arg));
            next_token(rest, extra, sizeof(extra));
            if (arg[0] && !extra[0]) {
                /* A lone dc file is the luminance layout's write. */
                Sh2Pair *pair = &pairs[count++];
                snprintf(pair->dc, MAX_PATH, "%s", arg);
                pair->lum[0] = '\0';
                const char *dot = strrchr(arg, '.');
                int stem = dot ? (int)(dot - arg) : (int)strlen(arg);
                fprintf(out, "    lightmap_image_write_sh2 %s", arg);
                for (int c = 0; c < 3; c++) {
                    snprintf(pair->color[c], MAX_PATH, "%.*s%s.shim%s", stem, arg, color_suffix[c], dot ? dot : "");
                    fprintf(out, " %s", pair->color[c]);
                }
                fprintf(out, "\n");
                continue;
            }
        }
        fputs(line, out);
    }
    fclose(in);
    return fclose(out) == 0 ? count : -1;
}

int main(void)
{
    char directory[MAX_PATH];
    DWORD length = GetModuleFileNameA(NULL, directory, sizeof(directory));
    char *separator = length && length < sizeof(directory) ? strrchr(directory, '\\') : NULL;
    if (separator == NULL) {
        fprintf(stderr, "vrad3 shim: cannot resolve executable directory\n");
        return 1;
    }
    *separator = '\0';

    /* Find the script argument and rewrite it beside the original. */
    int argc;
    LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    char script[MAX_PATH] = "", shim_script[MAX_PATH] = "";
    for (int i = 1; argv && i + 1 < argc; i++)
        if (wcscmp(argv[i], L"-script") == 0)
            WideCharToMultiByte(CP_UTF8, 0, argv[i + 1], -1, script, sizeof(script), NULL, NULL);
    Sh2Pair pairs[MAX_PAIRS];
    int pair_count = 0;
    if (script[0]) {
        snprintf(shim_script, sizeof(shim_script), "%s.shim", script);
        pair_count = rewrite_script(script, shim_script, pairs);
        if (pair_count < 0) {
            fprintf(stderr, "vrad3 shim: cannot rewrite %s, running it unchanged\n", script);
            shim_script[0] = '\0';
            pair_count = 0;
        }
    }

    /* Rebuild the command line for the real tool, swapping the script. */
    static wchar_t command_line[32768];
    _snwprintf(command_line, 32768, L"\"%hs\\vrad3_base.exe\"", directory);
    for (int i = 1; argv && i < argc; i++) {
        size_t used = wcslen(command_line);
        if (shim_script[0] && i > 1 && wcscmp(argv[i - 1], L"-script") == 0)
            _snwprintf(command_line + used, 32768 - used, L" \"%hs\"", shim_script);
        else
            _snwprintf(command_line + used, 32768 - used, L" \"%ls\"", argv[i]);
    }
    LocalFree(argv);

    STARTUPINFOW startup = {.cb = sizeof(startup)};
    PROCESS_INFORMATION process;
    if (!CreateProcessW(NULL, command_line, NULL, NULL, TRUE, 0, NULL, NULL, &startup, &process)) {
        fprintf(stderr, "vrad3 shim: cannot start vrad3_base.exe (%lu)\n", GetLastError());
        return 1;
    }
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    if (code != 0)
        return (int)code;

    for (int i = 0; i < pair_count; i++) {
        if (!pairs[i].lum[0])
            continue;
        if (!write_luminance(&pairs[i]))
            return 1;
        printf("vrad3 shim: wrote %s from %s and its color channels\n", pairs[i].lum, pairs[i].dc);
    }
    return 0;
}
