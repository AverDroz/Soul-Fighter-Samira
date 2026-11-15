/* Test host for the same exported ABI used by REPENTOGON. */
#define UNICODE
#include <windows.h>
int main(void) {
    HMODULE dll=LoadLibraryW(L"zhlSamiraCompanion.dll");
    if(!dll)return 2;
    int (*init)(void)=(int(*)(void))GetProcAddress(dll,"ModInit");
    if(!init)return 3;
    if(init()||init())return 4; /* repeated initialization must be harmless */
    Sleep(60000);
    return 0;
}
