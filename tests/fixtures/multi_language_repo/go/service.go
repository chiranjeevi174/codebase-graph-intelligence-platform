package service

import "fmt"

type ServiceInterface interface {
    DoWork()
}

type ServiceStruct struct {
    Name string
}

func (s *ServiceStruct) DoWork() {
    fmt.Println("Doing work in Go")
}

func NewService(name string) *ServiceStruct {
    return &ServiceStruct{Name: name}
}
