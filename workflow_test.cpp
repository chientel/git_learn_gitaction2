#include <iostream>

constexpr int EXIT_SUCCESS_CODE = 0;

void printWorkflowStatus()
{
    const char* MESSAGE = "GitHub Actions workflow test";
    std::cout << MESSAGE << '\n';
}

int main()
{
    printWorkflowStatus();
    
    return EXIT_SUCCESS_CODE;
}
