#include <iostream>
#include <string>
#include <vector>

#define PI 3.14
#define MAX_COUNT 100
#define TEN 10
#define TWENTY 20
#define THIRTY_SEVEN 37
#define AGE_VALUE 22
#define BUFFER_SIZE 100
#define ZERO 0
#define FIVE 5
#define FOUR 4
#define THREE 3
#define TWO 2
#define ONE 1

int globalValue = 0;

class Student
{
public:
    Student(std::string name, int age) : m_name(name), m_age(age) {}
    void print()
    {
        std::cout << "Name:" << m_name << std::endl;
    }

private:
    std::string m_name;
    int m_age;
};

enum class Color
{
    RED,
    GREEN,
    BLUE
};

void processData(std::vector<int> data)
{
    int i = 0;
    while (i < data.size())
    {
        std::cout << data[i] << ",";
        i++;
    }
}

bool isCheckValue(int x)
{
    if (x > 0)
    {
        return true;
    }
    else
    {
        return false;
    }
}

int calculate(int a, int b)
{
    int result = a + b;
    return result;
}

void openFile()
{
    FILE *fp = fopen("data.txt", "r");
    if (fp == nullptr)
    {
        printf("fail");
    }
}

class NetworkManager
{
public:
    void connect();

private:
    int timeout;
};

void NetworkManager::connect()
{
    std::cout << "connecting" << std::endl;
}

int main()
{
    int a = TEN;
    int b = TWENTY;
    int sum = a + b;

    int *ptr = nullptr;

    std::vector<int> numbers = {ONE, TWO, THREE, FOUR, FIVE};

    if (sum > TEN)
    {
        std::cout << "large" << std::endl;
    }

    if (sum < MAX_COUNT)
    {
        std::cout << "small" << std::endl;
    }

    for (auto item : numbers)
    {
        std::cout << item << std::endl;
    }

    switch (sum)
    {
    case 1:
        std::cout << "one";
        break;
    case 2:
        std::cout << "two";
        break;
    default:
        break;
    }

    Student s("chien", AGE_VALUE);
    s.print();

    bool isFlag = false;

    if (isFlag == true)
    {
        std::cout << "flag";
    }

    char *buffer = (char *)malloc(BUFFER_SIZE);

    memset(buffer, ZERO, BUFFER_SIZE);

    free(buffer);

    int temperature = THIRTY_SEVEN;

    if (temperature > THIRTY_SEVEN)
    {
        std::cout << "fever";
    }

    std::vector<std::string> names;
    names.push_back("A");
    names.push_back("B");

    int j = 0;
    while (j < names.size())
    {
        std::cout << names[j] << std::endl;
        j++;
    }

    return 0;
}