// SPDX-License-Identifier: GPL-2.0-or-later
// Exercise genuine Blender allocation APIs in both upstream implementations.
#include "MEM_guardedalloc.h"
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <thread>
#include <vector>
#define VERIFY(x) do { if(!(x)) throw std::runtime_error("Blender allocator: " #x); } while(false)
namespace {
struct Tracked {
  int *destructed;
  explicit Tracked(int *value):destructed(value){}
  ~Tracked(){++*destructed;}
};
void suite(){
  const size_t before=MEM_get_memory_in_use();
  const unsigned blocks=MEM_get_memory_blocks_in_use();
  auto *data=MEM_new_array_zeroed<uint32_t>(256,"Render zeroed array test");
  VERIFY(data!=nullptr);VERIFY(MEM_allocN_len(data)>=256*sizeof(uint32_t));
  VERIFY(MEM_get_memory_blocks_in_use()==blocks+1);
  VERIFY(MEM_get_memory_in_use()>=before+256*sizeof(uint32_t));
  for(int i=0;i<256;++i)VERIFY(data[i]==0);
  data[17]=0x12345678u;
  void *grown=MEM_realloc_zeroed_id(data,512*sizeof(uint32_t),"Render grow test");
  auto *resized=static_cast<uint32_t*>(grown);VERIFY(resized[17]==0x12345678u);
  for(int i=256;i<512;++i)VERIFY(resized[i]==0);
  MEM_delete(resized);
  void *aligned=MEM_new_uninitialized_aligned(257,64,"Render aligned allocation");
  VERIFY(aligned!=nullptr);VERIFY(reinterpret_cast<uintptr_t>(aligned)%64==0);
  MEM_delete_void(aligned);
  int destructed=0;auto *object=MEM_new<Tracked>("Render destructor test",&destructed);
  MEM_delete(object);VERIFY(destructed==1);
  std::vector<std::thread> workers;
  for(int t=0;t<4;++t)workers.emplace_back([]{
    for(int k=0;k<200;++k){auto *v=MEM_new_array_uninitialized<unsigned char>(128,"Render concurrent test");v[0]=1;MEM_delete(v);}
  });
  for(auto &worker:workers)worker.join();
  VERIFY(MEM_consistency_check());
  VERIFY(MEM_get_memory_in_use()==before);
  VERIFY(MEM_get_memory_blocks_in_use()==blocks);
}
}
int main(){
  MEM_init_memleak_detection();MEM_enable_fail_on_memleak();
  MEM_use_lockfree_allocator();suite();
  MEM_use_guarded_allocator();suite();
  MEM_use_lockfree_allocator();
  std::puts("PASS original Blender guardedalloc: zeroing, tracking, resizing, alignment, destructors, threads and leak-free cleanup");
}
