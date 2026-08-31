import asyncio

async def Func1(Name: str):
    print (f"Hello {Name}\n")
    await asyncio.sleep(2)
    print (f"Goodbye: {Name}\n")

async def Func2(Food:str):
    print (f"My favorite food is: {Food}\n")
    await asyncio.sleep(1)
    print (f"Continuing function 2")

async def main():
    await asyncio.gather (Func1("Siddharth Begwani"), Func2("Papri chaat"))

asyncio.run(main())

async def main():
    Task1 = asyncio.create_task(Func1("Siddharth Begwani"))
    Task2 = asyncio.create_task(Func2("Papri chaat"))
    await asyncio.gather(*[Task1, Task2])

asyncio.run(main())