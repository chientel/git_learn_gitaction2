#include<iostream>
#include<vector>
#include<string>
using namespace std;

#define pi 3.14
#define MAX_COUNT 100

int globalvalue=0;

class student{
public:
student(string name,int age):m_name(name),m_age(age){}
void print(){cout<<"Name:"<<m_name<<endl;}

private:
string m_name;
int m_age;
};

enum Color{
RED,
GREEN,
BLUE
};

void ProcessData(vector<int> data){
for(int i=0;i<data.size();i++){
cout<<data[i]<<",";
}
}

bool checkvalue(int x){ if(x>0) return true; else return false; }

int Calculate(int a,int b){
int result=a+b;
return result;
}

void openfile(){
FILE *fp=fopen("data.txt","r");
if(fp==NULL){
printf("fail");
}
}

class NetworkManager{
public:
void connect();
private:
int timeout;
};

void NetworkManager::connect(){
cout<<"connecting"<<endl;
}

int main(){

int a=10;
int b=20;
int sum=a+b;

int* ptr = NULL;

vector<int>numbers={1,2,3,4,5};

if(sum>10){
cout<<"large"<<endl;
}

if(sum<100) cout<<"small"<<endl;

for(auto item:numbers){
cout<<item<<endl;
}

switch(sum){
case 1:
cout<<"one";
break;
case 2:
cout<<"two";
break;
}

student s("chien",22);
s.print();

bool flag=false;

if(flag==true){
cout<<"flag";
}

char* buffer=(char*)malloc(100);

memset(buffer,0,100);

free(buffer);

int temperature = 37;

if(temperature>37){
cout<<"fever";
}

vector<string> names;
names.push_back("A");
names.push_back("B");

for(int i=0;i<names.size();i++){
cout<<names[i]<<endl;
}

return 0;
}